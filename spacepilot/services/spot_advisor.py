"""Spot Advisor service querying live AWS EC2 spot pricing and interruption risk."""
from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from spacepilot.paths import user_data_dir

logger = logging.getLogger(__name__)

VANTAGE_INSTANCES_URL = "https://instances.vantage.sh/instances.json"
SPOT_ADVISOR_URL = "https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json"
CACHE_TTL_SECONDS = 3600  # 1 hour local disk cache

INTERRUPTION_RATES = {
    0: "<5%",
    1: "5-10%",
    2: "10-15%",
    3: "15-20%",
    4: ">20%",
}


@dataclass(frozen=True)
class SpotAdvisorQuote:
    """Consolidated pricing, hardware, and interruption risk for an EC2 instance."""
    instance_type: str
    vcpu: int
    ram_gb: float
    gpu_name: str
    gpu_count: int
    gpu_memory_gb: float
    total_vram_gb: float
    ondemand_price_usd: float
    spot_price_est_usd: Optional[float]
    savings_pct: int
    interruption_risk: str
    region: str


def _cache_path(filename: str) -> Path:
    cache_dir = user_data_dir() / "cache" / "spot_advisor"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / filename


def fetch_vantage_data(
    timeout: int = 25,
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, Any]]:
    """Fetch global EC2 instance catalog with gzip compression and 1-hour caching."""
    cache_file = _cache_path("vantage_instances.json")
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            if on_progress:
                on_progress("Loading cached EC2 instance catalog...")
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    if on_progress:
        on_progress("Downloading AWS EC2 hardware specs & pricing from Vantage (compressed)...")

    req = urllib.request.Request(
        VANTAGE_INSTANCES_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SpacePilot/2.9.0)",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_encoding = resp.info().get("Content-Encoding", "").lower()
        raw_bytes = resp.read()
        if "gzip" in content_encoding:
            raw_bytes = gzip.decompress(raw_bytes)
        text = raw_bytes.decode("utf-8")
        data = json.loads(text)
        try:
            cache_file.write_text(text, encoding="utf-8")
        except Exception as exc:
            logger.debug("Failed to write vantage cache: %s", exc)
        return data


def fetch_spot_advisor_data(
    region: str = "us-east-1",
    timeout: int = 15,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Fetch AWS Spot Bid Advisor interruption rates and savings percentages."""
    cache_file = _cache_path(f"spot_advisor_{region}.json")
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            if on_progress:
                on_progress(f"Loading cached AWS Spot Advisor data ({region})...")
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    if on_progress:
        on_progress(f"Fetching live AWS Spot interruption rates for {region}...")

    req = urllib.request.Request(
        SPOT_ADVISOR_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SpacePilot/2.9.0)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw_text = resp.read().decode("utf-8")
        data = json.loads(raw_text)
        parsed = data.get("spot_advisor", {}).get(region, {}).get("Linux", {})
        try:
            cache_file.write_text(json.dumps(parsed), encoding="utf-8")
        except Exception as exc:
            logger.debug("Failed to write spot advisor cache: %s", exc)
        return parsed


def get_spot_intelligence(
    *,
    gpu: Optional[str] = None,
    min_vram_gb: Optional[float] = None,
    region: str = "us-east-1",
    sort_by: str = "price",
    timeout: int = 25,
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[SpotAdvisorQuote]:
    """Query and filter live spot pricing and interruption frequency."""
    vantage_data = fetch_vantage_data(timeout=timeout, on_progress=on_progress)
    advisor_data = fetch_spot_advisor_data(region=region, timeout=timeout, on_progress=on_progress)

    if on_progress:
        on_progress("Filtering and ranking matching GPU instances...")

    quotes: List[SpotAdvisorQuote] = []
    gpu_filter = gpu.strip().upper() if gpu else None

    known_specs: Dict[str, Dict[str, Any]] = {
        "g6e.xlarge": {"vcpu": 4, "ram": 32.0, "gpu_name": "L40S", "gpu_count": 1, "vram": 48.0},
        "g6e.2xlarge": {"vcpu": 8, "ram": 64.0, "gpu_name": "L40S", "gpu_count": 1, "vram": 48.0},
        "g6e.4xlarge": {"vcpu": 16, "ram": 128.0, "gpu_name": "L40S", "gpu_count": 1, "vram": 48.0},
        "g6e.8xlarge": {"vcpu": 32, "ram": 256.0, "gpu_name": "L40S", "gpu_count": 1, "vram": 48.0},
        "g6e.12xlarge": {"vcpu": 48, "ram": 384.0, "gpu_name": "L40S", "gpu_count": 4, "vram": 48.0},
        "g6e.16xlarge": {"vcpu": 64, "ram": 512.0, "gpu_name": "L40S", "gpu_count": 1, "vram": 48.0},
        "g6e.24xlarge": {"vcpu": 96, "ram": 768.0, "gpu_name": "L40S", "gpu_count": 4, "vram": 48.0},
        "g6e.48xlarge": {"vcpu": 192, "ram": 1536.0, "gpu_name": "L40S", "gpu_count": 8, "vram": 48.0},
        "g5.xlarge": {"vcpu": 4, "ram": 16.0, "gpu_name": "A10G", "gpu_count": 1, "vram": 24.0},
        "g5.2xlarge": {"vcpu": 8, "ram": 32.0, "gpu_name": "A10G", "gpu_count": 1, "vram": 24.0},
        "g5.4xlarge": {"vcpu": 16, "ram": 64.0, "gpu_name": "A10G", "gpu_count": 1, "vram": 24.0},
        "g6.xlarge": {"vcpu": 4, "ram": 16.0, "gpu_name": "L4", "gpu_count": 1, "vram": 24.0},
        "g6.2xlarge": {"vcpu": 8, "ram": 32.0, "gpu_name": "L4", "gpu_count": 1, "vram": 24.0},
        "g6.4xlarge": {"vcpu": 16, "ram": 64.0, "gpu_name": "L4", "gpu_count": 1, "vram": 24.0},
        "p4d.24xlarge": {"vcpu": 96, "ram": 1152.0, "gpu_name": "A100", "gpu_count": 8, "vram": 40.0},
        "p5.48xlarge": {"vcpu": 192, "ram": 2048.0, "gpu_name": "H100", "gpu_count": 8, "vram": 80.0},
    }

    for item in vantage_data:
        itype = str(item.get("instance_type", ""))
        pricing = item.get("pricing", {}).get(region, {}).get("linux", {})
        ondemand_raw = pricing.get("ondemand")
        if not ondemand_raw:
            continue

        ondemand_usd = float(ondemand_raw)
        spec = known_specs.get(itype, {})

        vcpu = int(item.get("vcpus") or item.get("vcpu") or spec.get("vcpu", 0))
        ram_gb = float(item.get("memory") or spec.get("ram", 0.0))
        gpu_count = int(item.get("gpu") or spec.get("gpu_count", 0))
        gpu_name = str(item.get("gpu_name") or spec.get("gpu_name", ""))
        gpu_mem_gb = float(item.get("gpu_memory") or spec.get("vram", 0.0))
        total_vram_gb = gpu_count * gpu_mem_gb

        if gpu_count <= 0 and not spec:
            continue

        if gpu_filter:
            target_matches = (
                gpu_filter in gpu_name.upper()
                or gpu_filter in itype.upper()
                or (gpu_filter == "L40S" and itype.startswith("g6e."))
                or (gpu_filter == "A10G" and itype.startswith("g5."))
                or (gpu_filter == "L4" and itype.startswith("g6."))
            )
            if not target_matches:
                continue

        if min_vram_gb is not None and total_vram_gb < min_vram_gb:
            continue

        adv_info = advisor_data.get(itype, {})
        savings_pct = int(adv_info.get("s", 0))
        risk_code = adv_info.get("r", -1)
        interruption_risk = INTERRUPTION_RATES.get(risk_code, "N/A")

        spot_est_usd: Optional[float] = None
        if savings_pct > 0:
            spot_est_usd = round(ondemand_usd * (1.0 - (savings_pct / 100.0)), 4)
        elif pricing.get("spot"):
            spot_est_usd = round(float(pricing["spot"]), 4)

        quotes.append(
            SpotAdvisorQuote(
                instance_type=itype,
                vcpu=vcpu,
                ram_gb=ram_gb,
                gpu_name=gpu_name or "GPU",
                gpu_count=gpu_count,
                gpu_memory_gb=gpu_mem_gb,
                total_vram_gb=total_vram_gb,
                ondemand_price_usd=ondemand_usd,
                spot_price_est_usd=spot_est_usd,
                savings_pct=savings_pct,
                interruption_risk=interruption_risk,
                region=region,
            )
        )

    if sort_by == "price":
        quotes.sort(key=lambda q: (q.spot_price_est_usd or q.ondemand_price_usd, q.ondemand_price_usd))
    elif sort_by == "vram":
        quotes.sort(key=lambda q: (-q.total_vram_gb, q.spot_price_est_usd or q.ondemand_price_usd))
    elif sort_by == "interruption":
        risk_order = {"<5%": 0, "5-10%": 1, "10-15%": 2, "15-20%": 3, ">20%": 4, "N/A": 5}
        quotes.sort(key=lambda q: (risk_order.get(q.interruption_risk, 5), q.spot_price_est_usd or q.ondemand_price_usd))
    else:
        quotes.sort(key=lambda q: q.instance_type)

    return quotes
