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
        self.responses = {"sts get-caller-identity": json.dumps({"Account": "842954813809"})}

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
    mock_client = MockAWSClient()
    mock_client.set_response("ssm get-parameter", "ami-dlami-mock123")
    mock_client.set_response("--dry-run", RuntimeError("DryRunOperation"))
    result = request_spot_instance("g6e.2xlarge", "key", dry_run=True, aws_client=mock_client)
    assert result.state == "dry_run"
    assert result.public_ip is None
    assert result.ssh_command is None
    assert "sts" in mock_client.commands_run[0]
    assert all("--dry-run" in cmd for cmd in mock_client.commands_run if "run-instances" in cmd)


def test_dry_run_rejects_wrong_account():
    mock_client = MockAWSClient()
    mock_client.set_response("sts get-caller-identity", json.dumps({"Account": "529738799911"}))
    with pytest.raises(ValueError, match="account"):
        request_spot_instance("g6e.2xlarge", "key", dry_run=True, aws_client=mock_client)
    assert not any("run-instances" in cmd for cmd in mock_client.commands_run)


def test_live_launch_is_gated():
    mock_client = MockAWSClient()
    with pytest.raises(ValueError, match="budget"):
        request_spot_instance("g6e.2xlarge", "key", dry_run=False, aws_client=mock_client)
    assert not mock_client.commands_run


def test_subprocess_always_names_profile_and_region(monkeypatch):
    from types import SimpleNamespace
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")
    monkeypatch.setattr("spacepilot.services.aws_fleet_launcher.subprocess.run", run)
    SubprocessAWSClient().run_aws_command(["sts", "get-caller-identity"])
    assert calls[0][:5] == ["aws", "--profile", "antigravity-dev-user", "--region", "us-east-1"]
    with pytest.raises(ValueError, match="profile"):
        SubprocessAWSClient(profile="katana")
