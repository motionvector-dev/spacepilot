"""Tests for spacepilot spot CLI and SpotAdvisor service."""
import pytest
from unittest.mock import patch
from spacepilot.services.spot_advisor import get_spot_intelligence, SpotAdvisorQuote
from spacepilot.cli import main


MOCK_VANTAGE_DATA = [
    {
        "instance_type": "g6e.2xlarge",
        "vcpu": 8,
        "memory": 64,
        "gpu": 1,
        "gpu_name": "L40S",
        "gpu_memory": 48,
        "pricing": {
            "us-east-1": {
                "linux": {
                    "ondemand": "2.242",
                    "spot": "1.031"
                }
            }
        }
    },
    {
        "instance_type": "g5.2xlarge",
        "vcpu": 8,
        "memory": 32,
        "gpu": 1,
        "gpu_name": "A10G",
        "gpu_memory": 24,
        "pricing": {
            "us-east-1": {
                "linux": {
                    "ondemand": "1.212",
                    "spot": "0.461"
                }
            }
        }
    }
]

MOCK_ADVISOR_DATA = {
    "g6e.2xlarge": {"s": 54, "r": 1},
    "g5.2xlarge": {"s": 62, "r": 3}
}


@patch("spacepilot.services.spot_advisor.fetch_vantage_data", return_value=MOCK_VANTAGE_DATA)
@patch("spacepilot.services.spot_advisor.fetch_spot_advisor_data", return_value=MOCK_ADVISOR_DATA)
def test_get_spot_intelligence_filter_gpu(mock_adv, mock_vantage):
    quotes = get_spot_intelligence(gpu="L40S")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.instance_type == "g6e.2xlarge"
    assert q.gpu_name == "L40S"
    assert q.interruption_risk == "5-10%"
    assert q.savings_pct == 54


@patch("spacepilot.services.spot_advisor.fetch_vantage_data", return_value=MOCK_VANTAGE_DATA)
@patch("spacepilot.services.spot_advisor.fetch_spot_advisor_data", return_value=MOCK_ADVISOR_DATA)
def test_get_spot_intelligence_min_vram(mock_adv, mock_vantage):
    quotes = get_spot_intelligence(min_vram_gb=40)
    assert len(quotes) == 1
    assert quotes[0].instance_type == "g6e.2xlarge"


@patch("spacepilot.services.spot_advisor.fetch_vantage_data", return_value=MOCK_VANTAGE_DATA)
@patch("spacepilot.services.spot_advisor.fetch_spot_advisor_data", return_value=MOCK_ADVISOR_DATA)
def test_cli_spot_subcommand_runs(mock_adv, mock_vantage, capsys):
    status = main(["spot", "--gpu", "L40S"])
    assert status == 0
    captured = capsys.readouterr()
    assert "g6e.2xlarge" in captured.out
    assert "1x L40S" in captured.out
    assert "5-10%" in captured.out
