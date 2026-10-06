"""Unit tests for AWS Fleet Launcher service."""

import json
import pytest
from spacepilot.services.aws_fleet_launcher import (
    AWSClientInterface,
    InstanceConnectionTelemetry,
    SpotPriceQuote,
    SubprocessAWSClient,
    query_spot_prices,
    request_spot_instance,
    resolve_dlami_id,
)


class MockAWSClient(AWSClientInterface):
    """Deterministic mock of AWS CLI/API responses."""

    def __init__(self):
        self.commands_run = []
        self.responses = {}

    def set_response(self, prefix: str, output: str):
        self.responses[prefix] = output

    def run_aws_command(self, cmd: list[str], *, check: bool = True) -> str:
        self.commands_run.append(cmd)
        cmd_str = " ".join(cmd)
        for prefix, resp in self.responses.items():
            if prefix in cmd_str:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return ""


def test_query_spot_prices_parses_json_history():
    """query_spot_prices queries describe-spot-price-history and returns SpotPriceQuote list."""
    mock_client = MockAWSClient()
    mock_payload = {
        "SpotPriceHistory": [
            {
                "AvailabilityZone": "us-east-1a",
                "InstanceType": "g6e.4xlarge",
                "ProductDescription": "Linux/UNIX",
                "SpotPrice": "1.425000",
                "Timestamp": "2026-10-06T20:00:00.000Z",
            },
            {
                "AvailabilityZone": "us-east-1b",
                "InstanceType": "g6e.4xlarge",
                "ProductDescription": "Linux/UNIX",
                "SpotPrice": "1.520000",
                "Timestamp": "2026-10-06T20:00:00.000Z",
            },
            {
                "AvailabilityZone": "us-east-1a",
                "InstanceType": "g6e.8xlarge",
                "ProductDescription": "Linux/UNIX",
                "SpotPrice": "2.100000",
                "Timestamp": "2026-10-06T20:00:00.000Z",
            },
        ]
    }
    mock_client.set_response("describe-spot-price-history", json.dumps(mock_payload))

    quotes = query_spot_prices(
        ["g6e.4xlarge", "g6e.8xlarge"],
        aws_client=mock_client,
        max_results_per_type=1,
    )

    assert len(quotes) == 2
    assert quotes[0].instance_type == "g6e.4xlarge"
    assert quotes[0].spot_price_usd == 1.425
    assert quotes[0].availability_zone == "us-east-1a"
    assert quotes[1].instance_type == "g6e.8xlarge"
    assert quotes[1].spot_price_usd == 2.10
    assert any("describe-spot-price-history" in " ".join(c) for c in mock_client.commands_run)


def test_query_spot_prices_empty_list():
    """Empty instance types list returns empty quotes without running AWS commands."""
    mock_client = MockAWSClient()
    quotes = query_spot_prices([], aws_client=mock_client)
    assert quotes == []
    assert len(mock_client.commands_run) == 0


def test_resolve_dlami_id_from_ssm_parameter():
    """SSM parameter lookup resolves official DLAMI."""
    mock_client = MockAWSClient()
    mock_client.set_response("ssm get-parameter", "ami-0123456789abcdef0")

    ami_id = resolve_dlami_id(aws_client=mock_client)
    assert ami_id == "ami-0123456789abcdef0"
    assert any("ssm" in c for c in mock_client.commands_run)


def test_resolve_dlami_id_fallback_to_describe_images():
    """If SSM lookup fails, falls back to describe-images query."""
    mock_client = MockAWSClient()
    mock_client.set_response("ssm get-parameter", "")
    mock_client.set_response("describe-images", "ami-0fedcba9876543210")

    ami_id = resolve_dlami_id(aws_client=mock_client)
    assert ami_id == "ami-0fedcba9876543210"
    assert any("describe-images" in " ".join(c) for c in mock_client.commands_run)


def test_request_spot_instance_dry_run():
    """Dry run validates request and produces mock telemetry with zero cost."""
    mock_client = MockAWSClient()
    # AWS returns DryRunOperation error when dry-run succeeds
    mock_client.set_response(
        "--dry-run",
        RuntimeError("An error occurred (DryRunOperation) when calling the RunInstances operation: Request would have succeeded"),
    )

    telem = request_spot_instance(
        instance_type="g6e.4xlarge",
        key_name="my-key",
        key_file="/path/to/my-key.pem",
        dry_run=True,
        aws_client=mock_client,
    )

    assert isinstance(telem, InstanceConnectionTelemetry)
    assert telem.dry_run is True
    assert telem.state == "dry_run"
    assert telem.public_ip == "198.51.100.1"
    assert "ssh -i /path/to/my-key.pem ubuntu@198.51.100.1" in telem.ssh_command
    assert "-L 5000:localhost:5000" in telem.tunnel_command


def test_request_spot_instance_live_launch():
    """Live launch issues ec2 run-instances and returns connection telemetry."""
    mock_client = MockAWSClient()
    mock_client.set_response("ssm get-parameter", "ami-dlami-live")

    run_instances_payload = {
        "Instances": [
            {
                "InstanceId": "i-0987654321fedcba0",
                "InstanceType": "g6e.4xlarge",
                "State": {"Name": "pending"},
                "PublicIpAddress": "34.201.55.99",
                "LaunchTime": "2026-10-06T20:05:00.000Z",
            }
        ]
    }
    mock_client.set_response("run-instances", json.dumps(run_instances_payload))

    telem = request_spot_instance(
        instance_type="g6e.4xlarge",
        key_name="pluto-gpu-key-2026-07-26",
        key_file="/Users/saurabh/.ssh/pluto-gpu-key-2026-07-26.pem",
        dry_run=False,
        aws_client=mock_client,
    )

    assert telem.instance_id == "i-0987654321fedcba0"
    assert telem.state == "pending"
    assert telem.public_ip == "34.201.55.99"
    assert telem.ssh_command == "ssh -i /Users/saurabh/.ssh/pluto-gpu-key-2026-07-26.pem ubuntu@34.201.55.99"
    assert telem.tunnel_command == "ssh -i /Users/saurabh/.ssh/pluto-gpu-key-2026-07-26.pem -L 5000:localhost:5000 -L 8088:localhost:8088 ubuntu@34.201.55.99"
    assert telem.dry_run is False

    # Check that Spot market options and block device mapping were included
    launch_cmd = [c for c in mock_client.commands_run if "run-instances" in c][0]
    assert "--instance-market-options" in launch_cmd
    assert "--block-device-mappings" in launch_cmd
    assert "--image-id" in launch_cmd
    assert "ami-dlami-live" in launch_cmd
