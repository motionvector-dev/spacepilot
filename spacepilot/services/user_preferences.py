"""User preferences and model default configuration persistence.

Stores user preferences such as default GPU mapping per model in
`~/.spacepilot_config.json` without clobbering existing configuration settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from spacepilot.cli import CONFIG_FILE, load_config, save_config

PREFERENCES_KEY = "user_preferences"
DEFAULT_GPUS_KEY = "default_gpus"


def _read_raw_config(config_path: Path) -> Dict[str, Any]:
    """Read raw config file without merging DEFAULT_CONFIG defaults.

    This preserves the exact existing configuration keys on disk.
    """
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
    return {}


def get_default_gpu(model_id: str, *, config_path: Optional[Path] = None) -> Optional[str]:
    """Retrieve the persisted default GPU type for a given model_id.

    Args:
        model_id: Identifier of the model (e.g. 'ltx-video', 'wan-2.1-t2v-14b').
        config_path: Optional explicit configuration file path (defaults to CLI CONFIG_FILE).

    Returns:
        The configured GPU type string if present, otherwise None.
    """
    target = config_path if config_path is not None else CONFIG_FILE
    raw = _read_raw_config(target)
    # Check under "user_preferences" -> "default_gpus"
    prefs = raw.get(PREFERENCES_KEY, {})
    if isinstance(prefs, dict):
        gpu = prefs.get(DEFAULT_GPUS_KEY, {}).get(model_id)
        if isinstance(gpu, str) and gpu.strip():
            return gpu.strip()

    # Also check if top-level "default_gpus" or fallback load_config has it
    top_level_gpus = raw.get(DEFAULT_GPUS_KEY, {})
    if isinstance(top_level_gpus, dict):
        gpu = top_level_gpus.get(model_id)
        if isinstance(gpu, str) and gpu.strip():
            return gpu.strip()

    # Fallback to load_config() if config_path was None
    if config_path is None:
        full_cfg = load_config()
        full_prefs = full_cfg.get(PREFERENCES_KEY, {})
        if isinstance(full_prefs, dict):
            gpu = full_prefs.get(DEFAULT_GPUS_KEY, {}).get(model_id)
            if isinstance(gpu, str) and gpu.strip():
                return gpu.strip()
        gpu = full_cfg.get(DEFAULT_GPUS_KEY, {}).get(model_id)
        if isinstance(gpu, str) and gpu.strip():
            return gpu.strip()

    return None


def set_default_gpu(model_id: str, gpu_type: str, *, config_path: Optional[Path] = None) -> None:
    """Set and persist the default GPU type for a given model_id.

    Saves into `~/.spacepilot_config.json` without clobbering existing configuration keys.

    Args:
        model_id: Identifier of the model.
        gpu_type: Target GPU type name (e.g. 'a100-80gb', 'l40s', 'h100').
        config_path: Optional explicit configuration file path (defaults to CLI CONFIG_FILE).
    """
    target = config_path if config_path is not None else CONFIG_FILE
    raw = _read_raw_config(target)

    # If raw is empty and file doesn't exist, seed with load_config() to preserve expected defaults
    if not raw and not target.exists():
        raw = load_config()

    if PREFERENCES_KEY not in raw or not isinstance(raw[PREFERENCES_KEY], dict):
        raw[PREFERENCES_KEY] = {}

    prefs = raw[PREFERENCES_KEY]
    if DEFAULT_GPUS_KEY not in prefs or not isinstance(prefs[DEFAULT_GPUS_KEY], dict):
        prefs[DEFAULT_GPUS_KEY] = {}

    prefs[DEFAULT_GPUS_KEY][model_id] = gpu_type

    # Also maintain top-level default_gpus for direct accessibility
    if DEFAULT_GPUS_KEY not in raw or not isinstance(raw[DEFAULT_GPUS_KEY], dict):
        raw[DEFAULT_GPUS_KEY] = {}
    raw[DEFAULT_GPUS_KEY][model_id] = gpu_type

    if config_path is not None:
        import os
        import tempfile

        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                fd = -1
                json.dump(raw, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
            target.chmod(0o600)
        finally:
            if fd != -1:
                os.close(fd)
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
    else:
        save_config(raw)
