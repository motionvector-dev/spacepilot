"""AWS Fleet Launcher service for provisioning EC2 Spot/On-Demand GPU instances.

Provides mockable live spot pricing queries, EC2 spot/on-demand instance
requests using Deep Learning AMI, and telemetry connection extraction.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DLAMI_SSM_PARAMETER = (
    "/aws/service/ami-amazon-linux-latest/deep-learning-oss-gpu-base-al2023"
)
DEFAULT_DLAMI_NAME_FILTER = (
    "*Deep Learning Base OSS*2024*"
)


@dataclass(frozen=True)
class SpotPriceQuote:
    """Spot price quote for an instance type in an Availability Zone."""
    instance_type: str
    availability_zone: str
    spot_price_usd: float
    timestamp: str


@dataclass(frozen=True)
class InstanceConnectionTelemetry:
    """Telemetry information for connecting to a provisioned instance."""
    instance_id: str
    state: str
    public_ip: Optional[str]
    instance_type: str
    ssh_user: str
    ssh_command: Optional[str]
    tunnel_command: Optional[str]
    dry_run: bool = False
    details: Optional[Dict[str, Any]] = None


class AWSClientInterface:
    """Abstract/callable interface for AWS CLI or SDK command execution."""

    def run_aws_command(self, cmd: List[str], *, check: bool = True) -> str:
        raise NotImplementedError


logger = logging.getLogger(__name__)


class SubprocessAWSClient(AWSClientInterface):
    """Executes AWS CLI commands via subprocess."""

    def __init__(self, profile: str = "antigravity-dev-user", region: str = "us-east-1"):
        if profile not in {"default", "antigravity-dev-user"}:
            raise ValueError("AWS profile is not permitted")
        self.profile = profile
        self.region = region

    def run_aws_command(self, cmd: List[str], *, check: bool = True) -> str:
        base = ["aws"]
        if self.profile:
            base.extend(["--profile", self.profile])
        if self.region:
            base.extend(["--region", self.region])
        full_cmd = base + cmd
        logger.debug("Executing AWS command: %s", " ".join(full_cmd))
        res = subprocess.run(full_cmd, capture_output=True, text=True, check=False)
        if check and res.returncode != 0:
            logger.error("AWS command failed (%d): %s\nStderr: %s", res.returncode, " ".join(full_cmd), res.stderr.strip())
            raise RuntimeError(
                f"AWS command failed ({res.returncode}): {' '.join(full_cmd)}\n{res.stderr.strip()}"
            )
        logger.debug("AWS command completed (%d bytes)", len(res.stdout))
        return res.stdout.strip()


def query_spot_prices(
    instance_types: List[str],
    *,
    aws_client: Optional[AWSClientInterface] = None,
    product_descriptions: Optional[List[str]] = None,
    max_results_per_type: int = 1,
) -> List[SpotPriceQuote]:
    """Query live spot price history for specified EC2 instance types."""
    if not instance_types:
        return []

    client = aws_client or SubprocessAWSClient()
    descriptions = product_descriptions or ["Linux/UNIX"]

    cmd = [
        "ec2",
        "describe-spot-price-history",
        "--instance-types",
        *instance_types,
        "--product-descriptions",
        *descriptions,
        "--max-items",
        str(len(instance_types) * 5),
        "--output",
        "json",
    ]

    raw_output = client.run_aws_command(cmd)
    if not raw_output:
        return []

    data = json.loads(raw_output)
    history = data.get("SpotPriceHistory", [])

    seen_per_type: Dict[str, int] = {}
    quotes: List[SpotPriceQuote] = []

    for item in history:
        itype = item.get("InstanceType")
        az = item.get("AvailabilityZone", "")
        price = float(item.get("SpotPrice", 0.0))
        timestamp = item.get("Timestamp", "")
        count = seen_per_type.get(itype, 0)
        if count < max_results_per_type:
            quotes.append(
                SpotPriceQuote(
                    instance_type=itype,
                    availability_zone=az,
                    spot_price_usd=price,
                    timestamp=timestamp,
                )
            )
            seen_per_type[itype] = count + 1

    return quotes


def resolve_dlami_id(
    *,
    aws_client: Optional[AWSClientInterface] = None,
    ssm_parameter: str = DEFAULT_DLAMI_SSM_PARAMETER,
    name_filter: str = DEFAULT_DLAMI_NAME_FILTER,
) -> str:
    """Resolve the latest official Amazon Deep Learning AMI ID."""
    client = aws_client or SubprocessAWSClient()

    # Try SSM parameter first
    try:
        ssm_cmd = [
            "ssm",
            "get-parameter",
            "--name",
            ssm_parameter,
            "--query",
            "Parameter.Value",
            "--output",
            "text",
        ]
        ami_id = client.run_aws_command(ssm_cmd, check=False).strip()
        if ami_id and ami_id != "None" and not ami_id.startswith("error"):
            return ami_id
    except Exception:
        pass

    # Fallback to describe-images
    images_cmd = [
        "ec2",
        "describe-images",
        "--owners",
        "amazon",
        "--filters",
        f"Name=name,Values={name_filter}",
        "Name=state,Values=available",
        "--query",
        "reverse(sort_by(Images,&CreationDate))[0].ImageId",
        "--output",
        "text",
    ]
    ami_id = client.run_aws_command(images_cmd).strip()
    if not ami_id or ami_id == "None":
        raise RuntimeError("Could not resolve Deep Learning AMI ID from SSM or EC2 describe-images")
    return ami_id


def request_spot_instance(
    instance_type: str,
    key_name: str,
    *,
    key_file: Optional[str] = None,
    ami_id: Optional[str] = None,
    security_group_ids: Optional[List[str]] = None,
    disk_gb: int = 220,
    instance_name: str = "spacepilot-gpu-node",
    user_data_script: Optional[str] = None,
    dry_run: bool = False,
    market_type: str = "spot",
    aws_client: Optional[AWSClientInterface] = None,
    profile: str = "antigravity-dev-user",
    region: str = "us-east-1",
) -> InstanceConnectionTelemetry:
    """Request an EC2 Spot (or On-Demand) instance with Deep Learning AMI and key."""
    if not dry_run:
        raise ValueError("Live launch is gated until a dock budget and worker deployment exist")
    from spacepilot.services.gpu_recommender import AWS_GPU_CATALOG, DEFAULT_MAX_VCPU_QUOTA
    spec = AWS_GPU_CATALOG.get(instance_type)
    if spec is None or spec.vcpu > DEFAULT_MAX_VCPU_QUOTA:
        raise ValueError("Instance type exceeds the verified 8-vCPU quota or is unknown")
    if profile not in {"default", "antigravity-dev-user"} or region != "us-east-1":
        raise ValueError("AWS profile or region is not permitted")
    client = aws_client or SubprocessAWSClient(profile=profile, region=region)
    identity = json.loads(client.run_aws_command(["sts", "get-caller-identity", "--output", "json"]))
    if identity.get("Account") != "842954813809":
        raise ValueError("AWS account must be 842954813809")

    resolved_ami = ami_id or resolve_dlami_id(aws_client=client)

    if dry_run:
        # Dry run validates parameters without spinning up resources
        dry_run_cmd = [
            "ec2",
            "run-instances",
            "--image-id",
            resolved_ami,
            "--instance-type",
            instance_type,
            "--key-name",
            key_name,
            "--count",
            "1",
            "--dry-run",
        ]
        if market_type == "spot":
            dry_run_cmd.extend(["--instance-market-options", '{"MarketType":"spot"}'])

        try:
            client.run_aws_command(dry_run_cmd)
        except RuntimeError as exc:
            # DryRunOperation is AWS's expected success response for --dry-run
            if "DryRunOperation" not in str(exc):
                raise

        mock_id = "i-dryrun" + "0" * 11
        mock_ip = None
        ssh_cmd = f"ssh -i {key_file} ubuntu@{mock_ip}" if key_file else f"ssh ubuntu@{mock_ip}"
        tunnel_cmd = (
            f"ssh -i {key_file} -L 5000:localhost:5000 -L 8088:localhost:8088 ubuntu@{mock_ip}"
            if key_file
            else f"ssh -L 5000:localhost:5000 -L 8088:localhost:8088 ubuntu@{mock_ip}"
        )

        return InstanceConnectionTelemetry(
            instance_id=mock_id,
            state="dry_run",
            public_ip=mock_ip,
            instance_type=instance_type,
            ssh_user="ubuntu",
            ssh_command=None,
            tunnel_command=None,
            dry_run=True,
            details={"ami_id": resolved_ami, "market_type": market_type, "disk_gb": disk_gb},
        )
