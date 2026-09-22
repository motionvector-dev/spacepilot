#!/usr/bin/env python3
"""In-process GGUF Narrative Decomposition Driver.

Deconstructs screenplays, commercial scripts, and creative prompts into cinematic
storyboard scene beats with 3D camera trajectory vectors and locked character seeds.
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from spacepilot.api.contracts import SCENE_COUNT_MAX, SCENE_COUNT_MIN
from spacepilot.drivers.base import DriverSpec, InferenceDriver

logger = logging.getLogger("spacepilot.drivers.gguf")

CAMERA_TRAJECTORIES: List[Tuple[str, Dict[str, float]]] = [
    ("Dynamic Dolly In", {"pan": 0.0, "tilt": 0.0, "zoom": 1.4, "roll": 0.0, "orbit": 0.0}),
    ("Slow Pan Right", {"pan": 0.7, "tilt": 0.0, "zoom": 1.0, "roll": 0.0, "orbit": 0.0}),
    ("Low Angle Tilt Up", {"pan": 0.0, "tilt": 0.8, "zoom": 1.1, "roll": 0.0, "orbit": 0.0}),
    ("3D Cinematic Orbit", {"pan": 0.4, "tilt": -0.2, "zoom": 1.0, "roll": 0.1, "orbit": 25.0}),
    ("Macro Push In", {"pan": 0.0, "tilt": 0.0, "zoom": 1.8, "roll": 0.0, "orbit": 0.0}),
    ("Wide Aerial Sweep", {"pan": -0.5, "tilt": -0.4, "zoom": 0.9, "roll": -0.1, "orbit": -15.0}),
    ("Tracking Shot Left", {"pan": -0.8, "tilt": 0.0, "zoom": 1.0, "roll": 0.0, "orbit": 0.0}),
    ("Whip Pan & Pull Back", {"pan": 1.0, "tilt": 0.0, "zoom": 0.7, "roll": 0.2, "orbit": 0.0}),
]

SHOT_TYPES = [
    "Extreme Wide Establishing Shot",
    "Medium Tracking Shot",
    "Low Angle Hero Shot",
    "Over-The-Shoulder Perspective",
    "Macro Detail Close-Up",
    "Dutch Angle Dynamic Shot",
    "Cinematic Bird's Eye View",
    "High Contrast Silhouette Shot",
]

LIGHTING_STYLES = [
    "Anamorphic Golden Hour with subtle lens flares",
    "Volumetric Cyberpunk Neon with moody reflections",
    "Chiaroscuro high-contrast dramatic studio lighting",
    "Soft diffused Nordic morning sunlight",
    "Deep space starlight with iridescent rim lighting",
    "Moody stormy twilight with atmospheric volumetric fog",
    "Warm 35mm tungsten practicals and deep shadows",
    "Hyper-clean monochrome high-key futuristic lighting",
]

TRANSITIONS = [
    "Cross Dissolve",
    "Match Cut on Action",
    "Whip Pan Transition",
    "Light Bloom Dissolve",
    "Hard Cut on Beat",
    "Invisible Foreground Wipe",
    "Depth of Field Pull",
    "Fade to Black",
]


class GGUFDriver(InferenceDriver):
    """In-process GGUF narrative decomposition driver."""

    def __init__(
        self,
        driver_id: str = "qwen2.5-3b-instruct-gguf",
        model_path: Optional[str] = None,
        resident_vram_gb: float = 2.1,
    ) -> None:
        spec = DriverSpec(
            driver_id=driver_id,
            task="storyboard",
            backend="gguf",
            resident_vram_gb=resident_vram_gb,
            is_loaded=False,
        )
        super().__init__(spec)
        self.model_path = model_path
        self.resolved_revision: Optional[str] = None
        self._llm: Any = None

    def _discover_model_path(self) -> Optional[str]:
        """Resolve one explicit file or one concrete registry snapshot file."""
        from spacepilot.paths import env_value, resolve

        if self.model_path:
            if not Path(self.model_path).is_file():
                raise FileNotFoundError(f"explicit GGUF model does not exist: {self.model_path}")
            self.resolved_revision = None
            return self.model_path

        configured = env_value("SPACEPILOT_GGUF_MODEL", "PLUTO_GGUF_MODEL")
        if configured:
            if not Path(configured).is_file():
                raise FileNotFoundError(f"configured GGUF model does not exist: {configured}")
            self.resolved_revision = None
            return configured

        from spacepilot.model_registry import registry

        variant = registry().variant(self.driver_id)
        if variant is None or not variant.files:
            return None
        resolved = resolve(variant.repo, variant.revision, variant.files)
        if resolved is None:
            return None
        files = [path for path in resolved.files if path.suffix.lower() == ".gguf"]
        if len(files) != 1:
            return None
        self.resolved_revision = resolved.revision
        return str(files[0])

    def load(self) -> bool:
        """Load GGUF weights into memory / llama.cpp session."""
        try:
            m_path = self._discover_model_path()
            if not m_path:
                raise FileNotFoundError(
                    f"no cached GGUF weights are registered for {self.driver_id}")
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=m_path,
                n_ctx=4096,
                n_gpu_layers=-1,
                verbose=False,
            )
            logger.info("Loaded GGUF model from %s", m_path)
            self.spec.is_loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load GGUFDriver: {e}")
            self.spec.is_loaded = False
            return False

    def unload(self) -> bool:
        """Unload GGUF context and release memory."""
        self._llm = None
        self.spec.is_loaded = False
        return True

    @staticmethod
    def _parse_scenes(text: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse model-produced JSON. Invalid model output is a real failure."""
        body = text.strip()
        if body.startswith("```"):
            body = re.sub(r"^```(?:json)?\s*|\s*```$", "", body, flags=re.IGNORECASE)
        payload = json.loads(body)
        scenes = payload.get("scenes") if isinstance(payload, dict) else None
        if not isinstance(scenes, list) or len(scenes) != expected_count:
            raise ValueError(f"GGUF model returned {len(scenes) if isinstance(scenes, list) else 0} scenes; expected {expected_count}")
        required = {
            "scene_id", "scene_idx", "title", "duration_sec", "prompt",
            "camera_motion", "camera_vector", "shot_type", "lighting",
            "environment", "transition", "audio_cue", "character_seed",
        }
        for index, scene in enumerate(scenes):
            if not isinstance(scene, dict) or not required <= set(scene):
                missing = required - set(scene) if isinstance(scene, dict) else required
                raise ValueError(f"GGUF scene {index + 1} is missing {sorted(missing)}")
        return scenes

    def infer(
        self,
        script: str,
        scene_count: int = 6,
        target_duration_sec: float = 60.0,
        style: str = "cinematic",
        character_seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute narrative script deconstruction into structured scene beats.
        
        Args:
            script: Narrative script or high-level concept text.
            scene_count: Target number of storyboard scenes (4 to 10).
            target_duration_sec: Total duration in seconds (10.0 to 300.0).
            style: Directing style descriptor.
            character_seed: Optional locked random seed for character consistency.
            
        Returns:
            Dict containing status, source driver, locked seed, and scene beats list.
        """
        start_time = time.time()
        if not self.is_loaded:
            if not self.load():
                raise RuntimeError("GGUFDriver could not load real model weights")
        if self._llm is None:
            raise RuntimeError("GGUFDriver has no loaded llama.cpp session")
        if not script or not script.strip():
            raise ValueError("script cannot be empty")

        # Refuse rather than clamp; see the note in storyboard_decomposer.
        if not SCENE_COUNT_MIN <= scene_count <= SCENE_COUNT_MAX:
            raise ValueError(
                f"scene_count must be between {SCENE_COUNT_MIN} and "
                f"{SCENE_COUNT_MAX} (got {scene_count})"
            )
        base_seed = character_seed if character_seed is not None else abs(hash(script.strip())) % 1000000
        prompt = (
            "Return JSON only with one key, scenes, containing exactly "
            f"{scene_count} cinematic scene objects for the supplied script. "
            "Every object must contain scene_id, scene_idx, title, duration_sec, "
            "prompt, camera_motion, camera_vector (pan, tilt, zoom, roll, orbit), "
            "shot_type, lighting, environment, transition, audio_cue, "
            f"character_seed (always {base_seed}), and takes_ready. Total duration "
            f"must be {target_duration_sec} seconds. Style: {style}. Script:\n{script}"
        )
        response = self._llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            seed=base_seed,
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("llama.cpp returned no assistant content") from exc
        scenes = self._parse_scenes(content, scene_count)

        elapsed_sec = round(time.time() - start_time, 3)

        return {
            "status": "success",
            "driver_id": self.driver_id,
            "task": self.task,
            "backend": self.backend,
            "model_revision": self.resolved_revision,
            "source": f"gguf_driver ({self.driver_id})",
            "original_script": script,
            "style": style,
            "scene_count": len(scenes),
            "target_duration_sec": target_duration_sec,
            "total_duration_sec": sum(s["duration_sec"] for s in scenes),
            "character_seed": base_seed,
            "elapsed_sec": elapsed_sec,
            "scenes": scenes,
        }
