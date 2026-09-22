"""Central configuration settings for SpacePilot."""

import os
import secrets
from importlib import resources
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from spacepilot import __version__
from spacepilot.paths import checkout_root, env_value, outputs_dir, user_data_dir


def _resolve_repo_root() -> Path:
    """The checkout this package was imported from, or its own parent.

    In an install there is no repo root at all, and the walk used to stop on
    `site-packages/`'s parent — which is how `.studio_token` was written into
    `lib/python3.13/` and `web_dir` pointed at a directory that never existed.
    Nothing that ships or that gets written may derive from this any more; it
    remains only for the repo-local scripts (`infra/gpu-box.sh`) that genuinely
    have no meaning outside a checkout.
    """
    root = checkout_root()
    if root is not None:
        return root
    return Path(__file__).resolve().parent.parent.parent


REPO_ROOT = _resolve_repo_root()


def _package_web_dir() -> Path:
    """The frontend, found the way the registry is: by asking the package.

    `resources.files` is the package's own answer to "where am I" and stays
    right when it is installed, moved, or vendored. `REPO_ROOT / "web"` was a
    guess, and on `uv tool install` it guessed `lib/python3.13/web` — so every
    page the README advertises answered 500.
    """
    override = env_value("SPACEPILOT_WEB_DIR", "PLUTO_WEB_DIR", default="").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(str(resources.files("spacepilot"))) / "web"


def _state_root() -> Path:
    """Where per-user state (the studio token) is kept.

    A checkout keeps it in the checkout, exactly as before, so a dev's token
    survives where they expect it. An install keeps it under the user data
    directory — never inside the install tree, which is unbackuped and wiped
    by the next upgrade.
    """
    root = checkout_root()
    return root if root is not None else user_data_dir()


def _get_or_create_studio_token(root: Path) -> str:
    # An explicit token skips the file entirely, so nothing that merely imports
    # the settings mints one into the checkout. The test suite relies on this.
    explicit = env_value("SPACEPILOT_STUDIO_TOKEN", "PLUTO_STUDIO_TOKEN", default="").strip()
    if explicit:
        return explicit
    token_file = root / ".studio_token"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if token_file.exists():
        try:
            tok = token_file.read_text().strip()
            if tok:
                return tok
        except Exception:
            pass
    token = secrets.token_hex(32)
    try:
        token_file.write_text(token)
        token_file.chmod(0o600)
    except Exception:
        pass
    return token


class Settings(BaseModel):
    """Consolidated SpacePilot Settings."""

    app_name: str = "SpacePilot Studio"
    version: str = __version__

    root_dir: Path = Field(default_factory=lambda: REPO_ROOT)
    # `spacepilot.paths.outputs_dir` already answers this for the CLI and the
    # services: the override, then the checkout, then the user data directory.
    # Answering it a second time here is what made an installed server write
    # renders into site-packages' parent.
    outputs_dir: Path = Field(default_factory=outputs_dir)
    web_dir: Path = Field(default_factory=_package_web_dir)

    studio_token: str = Field(default_factory=lambda: _get_or_create_studio_token(_state_root()))
    local_worker_token: Optional[str] = Field(default_factory=lambda: os.environ.get("LOCAL_WORKER_TOKEN"))

    # Loopback by default. This server hands out a token that unlocks a shell
    # websocket, so publishing it to every interface put that shell on whatever
    # network the laptop happened to join.
    host: str = Field(
        default_factory=lambda: env_value("SPACEPILOT_STUDIO_HOST", "PLUTO_STUDIO_HOST", default="127.0.0.1")
    )
    port: int = Field(
        default_factory=lambda: int(
            env_value(
                "SPACEPILOT_STUDIO_PORT",
                "PLUTO_STUDIO_PORT",
                default=os.environ.get("PORT", "8088"),
            )
        )
    )

    # Audio defaults
    mlx_serve_url: str = Field(default_factory=lambda: os.environ.get("MLX_SERVE_URL", "http://127.0.0.1:11234"))
    music_model: str = Field(default_factory=lambda: os.environ.get("MUSIC_MODEL", "music_default"))
    voice_model: str = Field(default_factory=lambda: os.environ.get("VOICE_MODEL", "kokoro-v1.0"))
    music_target_lufs: int = Field(default_factory=lambda: int(os.environ.get("MUSIC_TARGET_LUFS", -16)))
    voice_peak_dbfs: float = Field(default_factory=lambda: float(os.environ.get("VOICE_PEAK_DBFS", -1.0)))
    ffmpeg_timeout_sec: int = Field(default_factory=lambda: int(os.environ.get("FFMPEG_TIMEOUT_SEC", 1800)))

    # Kokoro paths
    kokoro_model_path: Optional[str] = Field(
        default_factory=lambda: env_value("SPACEPILOT_KOKORO_MODEL", "PLUTO_KOKORO_MODEL")
    )
    kokoro_voices_path: Optional[str] = Field(
        default_factory=lambda: env_value("SPACEPILOT_KOKORO_VOICES", "PLUTO_KOKORO_VOICES")
    )

    # Set PLUTO_ALLOW_REMOTE=1 to serve something other than this machine.
    # It widens the bind and drops the Host guard together, because doing one
    # without the other yields a server that listens and then refuses.
    @property
    def local_only(self) -> bool:
        return env_value("SPACEPILOT_ALLOW_REMOTE", "PLUTO_ALLOW_REMOTE", default="").strip() not in (
            "1", "true", "yes"
        )

    # CORS
    @property
    def cors_origins(self) -> list[str]:
        return [
            f"http://localhost:{self.port}",
            f"http://127.0.0.1:{self.port}",
            f"http://spacepilot.localhost:{self.port}",
            f"http://pluto.localhost:{self.port}",
            "http://spacepilot.localhost",
            "https://spacepilot.localhost",
            "http://pluto.localhost",
            "https://pluto.localhost",
        ]


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
