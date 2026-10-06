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


class SubprocessAWSClient(AWSClientInterface):
    """Executes AWS CLI commands via subprocess."""

    def __init__(self, profile: Optional[str] = None, region: Optional[str] = None):
        self.profile = profile
        self.region = region

    def run_aws_command(self, cmd: List[str], *, check: bool = True) -> str:
        base = ["aws"]
        if self.profile:
            base.extend(["--profile", self.profile])
        if self.region:
            base.extend(["--region", self.region])
        full_cmd = base + cmd
        res = subprocess.run(full_cmd, capture_output=True, text=True, check=False)
        if check and res.returncode != 0:
            raise RuntimeError(
                f"AWS command failed ({res.returncode}): {' '.join(full_cmd)}\n{res.stderr.strip()}"
            )
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
) -> InstanceConnectionTelemetry:
    """Request an EC2 Spot (or On-Demand) instance with Deep Learning AMI and key."""
    client = aws_client or SubprocessAWSClient()

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
        mock_ip = "198.51.100.1"
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
            ssh_command=ssh_cmd,
            tunnel_command=tunnel_cmd,
            dry_run=True,
            details={"ami_id": resolved_ami, "market_type": market_type, "disk_gb": disk_gb},
        )

    # Live launch execution
    cmd = [
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
        "--block-device-mappings",
        (
            f'[{{"DeviceName":"/dev/sda1","Ebs":{{"VolumeSize":{disk_gb},'
            f'"VolumeType":"gp3","Throughput":500,"DeleteOnTermination":true}}}}]'
        ),
        "--tag-specifications",
        (
            f'ResourceType=instance,Tags=[{{Key=Name,Value={instance_name}}},'
            f'{{Key=ManagedBy,Value=spacepilot}},{{Key=Purpose,Value=video-inference}}]'
        ),
        "--metadata-options",
        "HttpTokens=required,HttpEndpoint=enabled",
        "--output",
        "json",
    ]

    if security_group_ids:
        cmd.extend(["--security-group-ids", *security_group_ids])

    if market_type == "spot":
        cmd.extend(["--instance-market-options", '{"MarketType":"spot"}'])

    if user_data_script:
        cmd.extend(["--user-data", user_data_script])

    raw_resp = client.run_aws_command(cmd)
    data = json.loads(raw_resp) if raw_resp else {}
    instances = data.get("Instances", [])
    if not instances:
        raise RuntimeError(f"run-instances succeeded but returned no instance records: {raw_resp}")

    inst = instances[0]
    inst_id = inst.get("InstanceId", "")
    state = inst.get("State", {}).get("Name", "pending")
    public_ip = inst.get("PublicIpAddress")

    ssh_cmd = (
        f"ssh -i {key_file} ubuntu@{public_ip}"
        if key_file and public_ip
        else (f"ssh ubuntu@{public_ip}" if public_ip else None)
    )
    tunnel_cmd = (
        f"ssh -i {key_file} -L 5000:localhost:5000 -L 8088:localhost:8088 ubuntu@{public_ip}"
        if key_file and public_ip
        else (
            f"ssh -L 5000:localhost:5000 -L 8088:localhost:8088 ubuntu@{public_ip}"
            if public_ip
            else None
        )
    )

    return InstanceConnectionTelemetry(
        instance_id=inst_id,
        state=state,
        public_ip=public_ip,
        instance_type=instance_type,
        ssh_user="ubuntu",
        ssh_command=ssh_cmd,
        tunnel_command=tunnel_cmd,
        dry_run=False,
        details=inst,
    )
