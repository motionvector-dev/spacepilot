"""Central configuration settings for SpacePilot."""

import os
import secrets
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from spacepilot.paths import env_value


def _resolve_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "spacepilot").exists() and ((current / "web").exists() or (current / "pyproject.toml").exists()):
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent.parent


REPO_ROOT = _resolve_repo_root()


def _get_or_create_studio_token(root: Path) -> str:
    token_file = root / ".studio_token"
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
    version: str = "2.8.0"

    root_dir: Path = Field(default_factory=lambda: REPO_ROOT)
    outputs_dir: Path = Field(
        default_factory=lambda: Path(
            env_value("SPACEPILOT_OUTPUTS_DIR", "PLUTO_OUTPUTS_DIR", default=str(REPO_ROOT / "outputs"))
        ).resolve()
    )
    web_dir: Path = Field(default_factory=lambda: REPO_ROOT / "web")

    studio_token: str = Field(default_factory=lambda: _get_or_create_studio_token(REPO_ROOT))
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
        origins = [
            f"http://localhost:{self.port}",
            f"http://127.0.0.1:{self.port}",
            f"http://spacepilot.localhost:{self.port}",
            f"http://pluto.localhost:{self.port}",
            "http://spacepilot.localhost",
            "https://spacepilot.localhost",
            "http://pluto.localhost",
            "https://pluto.localhost",
            "https://motionvector.dev",
            "https://spacepilot.dev",
        ]
        # The "Archie" air-drums demo (Chrome on-device Gemini Nano, calling
        # /api/speech/* from an https page) confirmed its real origin as
        # https://motionvector-air-drums.nandwana-saurabh619.chatgpt.site —
        # deliberately not hardcoded here: one consumer's domain doesn't
        # belong baked into SpacePilot's own source. Set it via
        # SPACEPILOT_EXTRA_CORS_ORIGINS when running the daemon for that demo.
        extra = env_value("SPACEPILOT_EXTRA_CORS_ORIGINS", "PLUTO_EXTRA_CORS_ORIGINS", default="")
        if extra.strip():
            origins.extend(o.strip() for o in extra.split(",") if o.strip())
        return origins


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
