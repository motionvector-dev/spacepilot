"""Ephemeral observations of this machine.

PICTURE is sampled state, never a database.  Each section carries the time of
its last successful observation.  A failed refresh retains that timestamp and
marks the value stale; it must not make old readiness look newly checked.
"""

from __future__ import annotations

import datetime as dt
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from spacepilot.device_probe import probe_local_device
from spacepilot.local_workers import local_worker_manager


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class _LastGood:
    value: Any
    observed_at: dt.datetime


class PictureSampler:
    """Sample independent sections while preserving honest ages on failure."""

    def __init__(
        self,
        *,
        system_probe: Callable[[], Any] = probe_local_device,
        worker_probe: Callable[[], Mapping[str, Any]] = local_worker_manager.get_status,
        identity_probe: Callable[[], Mapping[str, Any]] | None = None,
        clock: Callable[[], dt.datetime] = _utc_now,
    ) -> None:
        self.system_probe = system_probe
        self.worker_probe = worker_probe
        self.identity_probe = identity_probe
        self.clock = clock
        self._last_good: dict[str, _LastGood] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _normalise(value: Any) -> Any:
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if isinstance(value, Mapping):
            return dict(value)
        raise TypeError(f"picture probe returned unsupported {type(value).__name__}")

    def _section(self, name: str, probe: Callable[[], Any], now: dt.datetime) -> dict[str, Any]:
        try:
            value = self._normalise(probe())
        except Exception as exc:
            previous = self._last_good.get(name)
            return {
                "state": "stale" if previous is not None else "unknown",
                "value": previous.value if previous is not None else None,
                "observed_at": _iso(previous.observed_at) if previous is not None else None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        self._last_good[name] = _LastGood(value=value, observed_at=now)
        return {
            "state": "fresh",
            "value": value,
            "observed_at": _iso(now),
            "error": None,
        }

    def sample(self) -> dict[str, Any]:
        with self._lock:
            now = self.clock()
            picture = {
                "schema": 1,
                "sampled_at": _iso(now),
                "system": self._section("system", self.system_probe, now),
                "workers": self._section("workers", self.worker_probe, now),
            }
            if self.identity_probe is not None:
                picture["identity"] = self._section("identity", self.identity_probe, now)
            return picture
