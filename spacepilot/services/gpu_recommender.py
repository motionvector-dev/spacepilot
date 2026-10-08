"""GPU recommender service matching model working set & precision to AWS GPU instances."""

from dataclasses import dataclass
from typing import List, Optional, Union, Dict, Any

from spacepilot.model_registry import Variant


@dataclass(frozen=True)
class AWSInstanceSpec:
    instance_type: str
    gpu_name: str
    gpu_count: int
    vram_per_gpu_gb: float
    total_vram_gb: float
    vcpu: int
    ram_gb: float
    spot_hourly_usd: float
    ondemand_hourly_usd: float
    generation_speed_s_per_step: float  # Baseline generation latency metric (lower is faster)
    architecture: str  # "ada", "ampere", etc.


# Canonical AWS GPU instance catalog within our fleet scope
AWS_GPU_CATALOG: Dict[str, AWSInstanceSpec] = {
    "g6e.2xlarge": AWSInstanceSpec(
        instance_type="g6e.2xlarge", gpu_name="L40S", gpu_count=1,
        vram_per_gpu_gb=48.0, total_vram_gb=48.0, vcpu=8, ram_gb=64.0,
        spot_hourly_usd=0.75, ondemand_hourly_usd=0.0,
        generation_speed_s_per_step=0.45, architecture="ada",
    ),
    "g6e.4xlarge": AWSInstanceSpec(
        instance_type="g6e.4xlarge",
        gpu_name="L40S",
        gpu_count=1,
        vram_per_gpu_gb=48.0,
        total_vram_gb=48.0,
        vcpu=16,
        ram_gb=64.0,
        spot_hourly_usd=1.60,
        ondemand_hourly_usd=3.20,
        generation_speed_s_per_step=0.45,
        architecture="ada",
    ),
    "g6e.8xlarge": AWSInstanceSpec(
        instance_type="g6e.8xlarge",
        gpu_name="L40S",
        gpu_count=1,
        vram_per_gpu_gb=48.0,
        total_vram_gb=48.0,
        vcpu=32,
        ram_gb=128.0,
        spot_hourly_usd=2.35,
        ondemand_hourly_usd=4.70,
        generation_speed_s_per_step=0.42,
        architecture="ada",
    ),
    "g6e.12xlarge": AWSInstanceSpec(
        instance_type="g6e.12xlarge",
        gpu_name="L40S",
        gpu_count=4,
        vram_per_gpu_gb=48.0,
        total_vram_gb=192.0,
        vcpu=48,
        ram_gb=192.0,
        spot_hourly_usd=4.80,
        ondemand_hourly_usd=9.60,
        generation_speed_s_per_step=0.18,
        architecture="ada",
    ),
    "g5.2xlarge": AWSInstanceSpec(
        instance_type="g5.2xlarge",
        gpu_name="A10G",
        gpu_count=1,
        vram_per_gpu_gb=24.0,
        total_vram_gb=24.0,
        vcpu=8,
        ram_gb=32.0,
        spot_hourly_usd=0.76,
        ondemand_hourly_usd=1.21,
        generation_speed_s_per_step=0.95,
        architecture="ampere",
    ),
    "g5.4xlarge": AWSInstanceSpec(
        instance_type="g5.4xlarge",
        gpu_name="A10G",
        gpu_count=1,
        vram_per_gpu_gb=24.0,
        total_vram_gb=24.0,
        vcpu=16,
        ram_gb=64.0,
        spot_hourly_usd=1.21,
        ondemand_hourly_usd=1.62,
        generation_speed_s_per_step=0.90,
        architecture="ampere",
    ),
    "g6.4xlarge": AWSInstanceSpec(
        instance_type="g6.4xlarge",
        gpu_name="L4",
        gpu_count=1,
        vram_per_gpu_gb=24.0,
        total_vram_gb=24.0,
        vcpu=16,
        ram_gb=64.0,
        spot_hourly_usd=0.98,
        ondemand_hourly_usd=1.36,
        generation_speed_s_per_step=1.05,
        architecture="ada",
    ),
}

DEFAULT_MAX_VCPU_QUOTA = 8  # Verified account 842954813809, us-east-1, 2026-10-08


@dataclass(frozen=True)
class GPURecommendation:
    instance_spec: AWSInstanceSpec
    vram_margin_gb: float
    cost_performance_score: float
    fits_vram: bool
    fits_ram: bool
    fits_quota: bool
    notes: str

    @property
    def instance_type(self) -> str:
        return self.instance_spec.instance_type

    @property
    def spot_hourly_usd(self) -> float:
        return self.instance_spec.spot_hourly_usd

    @property
    def generation_speed_s_per_step(self) -> float:
        return self.instance_spec.generation_speed_s_per_step

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_type": self.instance_type,
            "gpu_name": self.instance_spec.gpu_name,
            "gpu_count": self.instance_spec.gpu_count,
            "total_vram_gb": self.instance_spec.total_vram_gb,
            "vcpu": self.instance_spec.vcpu,
            "ram_gb": self.instance_spec.ram_gb,
            "spot_hourly_usd": self.spot_hourly_usd,
            "ondemand_hourly_usd": self.instance_spec.ondemand_hourly_usd,
            "generation_speed_s_per_step": self.generation_speed_s_per_step,
            "vram_margin_gb": round(self.vram_margin_gb, 2),
            "cost_performance_score": round(self.cost_performance_score, 4),
            "fits_vram": self.fits_vram,
            "fits_ram": self.fits_ram,
            "fits_quota": self.fits_quota,
            "notes": self.notes,
        }


# GPU architecture performance weighting (L40S > A10G > L4)
ARCH_EFFICIENCY = {
    "L40S": 1.0,
    "A10G": 0.65,
    "L4": 0.55,
}


def recommend_gpus(
    target: Union[Variant, int, float],
    precision: Optional[str] = None,
    host_ram_required_bytes: Optional[int] = None,
    max_vcpu_quota: int = DEFAULT_MAX_VCPU_QUOTA,
    catalog: Optional[Dict[str, AWSInstanceSpec]] = None,
) -> List[GPURecommendation]:
    """
    Recommend and rank AWS GPU instances for a given model variant or working set size.

    Target can be:
      - A Variant instance from spacepilot.model_registry (or duck-typed object with working_set & precision)
      - An integer / float representing working_set_bytes

    Instances are filtered by:
      - Quota limit: spec.vcpu <= max_vcpu_quota
      - Capacity: instances where total VRAM (or VRAM + host offload RAM) can accommodate working set.

    Ranked by cost/performance score:
      Lower cost * latency gives optimal efficiency (normalized performance per dollar).
    """
    if catalog is None:
        catalog = AWS_GPU_CATALOG

    # Extract working set bytes and precision
    working_set_bytes: float = 0.0
    req_precision: str = (precision or "").lower()
    req_host_ram_bytes: float = float(host_ram_required_bytes or 0)

    if isinstance(target, (int, float)):
        working_set_bytes = float(target)
    elif hasattr(target, "working_set"):
        # Variant object
        ws = getattr(target, "working_set")
        if hasattr(ws, "value"):
            working_set_bytes = float(ws.value)
        elif hasattr(ws, "bytes"):
            working_set_bytes = float(ws.bytes)
        elif isinstance(ws, dict):
            working_set_bytes = float(ws.get("value", ws.get("bytes", 0)))
        if not req_precision and getattr(target, "precision", None):
            req_precision = str(target.precision).lower()
    elif isinstance(target, dict):
        working_set_bytes = float(target.get("working_set_bytes", target.get("working_set", 0)))
        if not req_precision and "precision" in target:
            req_precision = str(target["precision"]).lower()
    else:
        raise ValueError(f"Unsupported target type for GPU recommendation: {type(target)}")

    working_set_gb = working_set_bytes / (1024 ** 3)
    req_host_ram_gb = req_host_ram_bytes / (1024 ** 3)

    candidates: List[GPURecommendation] = []

    for spec in catalog.values():
        fits_quota = spec.vcpu <= max_vcpu_quota
        if not fits_quota:
            continue

        fits_vram = spec.total_vram_gb >= working_set_gb
        fits_ram = spec.ram_gb >= req_host_ram_gb if req_host_ram_gb > 0 else True
        vram_margin = spec.total_vram_gb - working_set_gb

        # If host RAM requirement is specified, instance MUST fit host RAM
        if req_host_ram_gb > 0 and not fits_ram:
            continue

        # Check offload scenario: if VRAM is insufficient but host RAM is requested/available
        is_offload_candidate = False
        if not fits_vram and req_host_ram_gb > 0:
            if fits_ram and spec.total_vram_gb >= 24.0:
                is_offload_candidate = True

        if not fits_vram and not is_offload_candidate:
            continue

        # Calculate cost/performance score
        arch_mult = ARCH_EFFICIENCY.get(spec.gpu_name, 0.5)
        effective_latency = spec.generation_speed_s_per_step / arch_mult
        if is_offload_candidate:
            effective_latency *= 2.0  # Host RAM offloading penalty

        # Cost-performance score: lower is better (spot rate * effective latency)
        # Spot price carries 1.25 exponent so that lower-cost single GPU boxes
        # are favored for budget/offload tiers over expensive multi-GPU clusters.
        score = (spec.spot_hourly_usd ** 1.25) * effective_latency

        notes = "Planning estimate, not a live price or measured speed. " + f"{spec.gpu_count}x {spec.gpu_name} ({spec.total_vram_gb:.0f}GB VRAM, {spec.ram_gb:.0f}GB RAM)"
        if is_offload_candidate:
            notes += " [Host RAM Offload]"
        elif vram_margin >= 0:
            notes += f" [Headroom: +{vram_margin:.1f}GB]"

        candidates.append(
            GPURecommendation(
                instance_spec=spec,
                vram_margin_gb=vram_margin,
                cost_performance_score=score,
                fits_vram=fits_vram,
                fits_ram=fits_ram,
                fits_quota=fits_quota,
                notes=notes,
            )
        )

    # Sort primarily by cost_performance_score ascending (best cost/perf first)
    candidates.sort(key=lambda r: (r.cost_performance_score, -r.vram_margin_gb))
    return candidates
