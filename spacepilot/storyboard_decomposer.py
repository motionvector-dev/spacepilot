#!/usr/bin/env python3
"""SpacePilot Gemini Storyboard & Script Decomposer

Deconstructs narrative scripts and high-level 60-second prompts into 6-8 cinematic
storyboard scenes with locked character seeds, 3D camera trajectory vectors, and
detailed spatial lighting prompts for batch generative video production.
"""

import os
import re
import json
import time
import logging
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger("spacepilot.storyboard")

CAMERA_MOTIONS = [
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


def decompose_script_rule_based(
    script: str,
    target_duration_sec: float = 60.0,
    scene_count: int = 6,
    style: str = "cinematic",
    character_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Algorithmic rule-based script decomposition engine for offline/fallback execution."""
    cleaned = script.strip()
    if not cleaned:
        cleaned = "A cinematic voyage across deep space through glowing nebulae into a futuristic cybernetic metropolis."

    # Clamp scene count between 4 and 10
    scene_count = max(4, min(10, scene_count))
    base_seed = character_seed or (abs(hash(cleaned)) % 1000000)
    per_scene_dur = round(target_duration_sec / scene_count, 1)

    # Break script into semantic chunks or sentences
    sentences = [s.strip() for s in re.split(r"[.\n;]+", cleaned) if len(s.strip()) > 5]
    if not sentences:
        sentences = [cleaned]

    scenes: List[Dict[str, Any]] = []
    titles = [
        "The Spark of Genesis",
        "Threshold of Discovery",
        "Ascension Through Turbulence",
        "The Inner Sanctum",
        "Climactic Resonance",
        "Convergence of Light",
        "Temporal Horizon",
        "Echoes of Eternity",
        "The New Frontier",
        "Coda: The Infinite Loop",
    ]

    for idx in range(scene_count):
        scene_num = idx + 1
        cam_motion_name, cam_vec = CAMERA_MOTIONS[idx % len(CAMERA_MOTIONS)]
        shot_type = SHOT_TYPES[idx % len(SHOT_TYPES)]
        lighting = LIGHTING_STYLES[idx % len(LIGHTING_STYLES)]
        transition = TRANSITIONS[idx % len(TRANSITIONS)]
        title = titles[idx % len(titles)]

        # Get relevant text chunk
        narrative_snippet = sentences[idx % len(sentences)]
        if len(sentences) <= idx:
            narrative_snippet = f"{cleaned} (Part {scene_num})"

        # Generate vivid, LTX-Video-compatible visual prompt
        prompt = (
            f"{shot_type} of {narrative_snippet}. {cam_motion_name}, {lighting}, "
            f"photorealistic 8k, highly detailed textures, masterpiece cinematic 35mm film grain."
        )

        audio_cue = f"Ambient SFX: {cam_motion_name.lower()} whoosh with {lighting.split()[0].lower()} atmospheric tone."

        scenes.append({
            "scene_id": f"scene_{scene_num:02d}",
            "scene_idx": scene_num,
            "title": title,
            "duration_sec": per_scene_dur,
            "prompt": prompt,
            "camera_motion": cam_motion_name,
            "camera_vector": cam_vec,
            "shot_type": shot_type,
            "lighting": lighting,
            "environment": f"Cinematic {style} environment",
            "transition": transition,
            "audio_cue": audio_cue,
            "character_seed": base_seed,  # Locked seed for character consistency
            "takes_ready": 0,
        })

    # Adjust last scene duration so total matches target exactly
    total_dur = sum(s["duration_sec"] for s in scenes)
    scenes[-1]["duration_sec"] = round(scenes[-1]["duration_sec"] + (target_duration_sec - total_dur), 1)

    return {
        "status": "success",
        "source": "heuristic_cinematic_engine",
        "original_script": script,
        "style": style,
        "scene_count": len(scenes),
        "target_duration_sec": target_duration_sec,
        "total_duration_sec": sum(s["duration_sec"] for s in scenes),
        "character_seed": base_seed,
        "scenes": scenes,
    }


def call_gemini_decompose_api(
    script: str,
    target_duration_sec: float = 60.0,
    scene_count: int = 6,
    style: str = "cinematic",
    model: str = "gemini-3.7-flash",
    api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Call Google Gemini API to deconstruct narrative into structured JSON scenes."""
    key = (
        api_key
        or os.environ.get("GEMINI_PRIMARY_API_KEY")
        or os.environ.get("GEMINI_SECONDARY_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if not key:
        return None

    # Supported fast model endpoints
    model_endpoint = model or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_endpoint}:generateContent?key={key}"

    system_instruction = (
        "You are an elite Hollywood Director and AI Cinematographer. Your job is to take a user prompt or script "
        f"and decompose it into exactly {scene_count} chronological cinematic storyboard scenes totaling {target_duration_sec}s. "
        "Each scene must have: scene_id, scene_idx, title, duration_sec, prompt (explicit spatial layout, lighting, camera movement, LTX-Video photorealistic style), "
        "camera_motion (e.g. Dynamic Dolly In, 3D Orbit, Slow Pan Right), camera_vector (pan, tilt, zoom, roll, orbit), shot_type, lighting, environment, transition, audio_cue. "
        "Output ONLY valid JSON adhering to the specified structure without markdown formatting or backticks."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\nScript to decompose:\n{script}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }

    try:
        resp = httpx.post(
            url,
            content=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=12.0,
        )
        # urlopen raised HTTPError on 4xx/5xx and the broad except below turned
        # that into the heuristic fallback. Keep the status a raise.
        resp.raise_for_status()
        data = resp.json()
        candidate_text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(candidate_text)
        
        # If Gemini returned a list of scenes or nested dict
        if isinstance(parsed, list):
            scenes = parsed
        elif isinstance(parsed, dict) and "scenes" in parsed:
            scenes = parsed["scenes"]
        else:
            scenes = [parsed]

        # Validate and normalize
        base_seed = abs(hash(script)) % 1000000
        for idx, sc in enumerate(scenes):
            sc["scene_idx"] = sc.get("scene_idx", idx + 1)
            sc["scene_id"] = sc.get("scene_id", f"scene_{idx+1:02d}")
            sc["character_seed"] = base_seed
            if "camera_vector" not in sc:
                _, sc["camera_vector"] = CAMERA_MOTIONS[idx % len(CAMERA_MOTIONS)]

        return {
            "status": "success",
            "source": f"gemini_api ({model_endpoint})",
            "original_script": script,
            "style": style,
            "scene_count": len(scenes),
            "target_duration_sec": target_duration_sec,
            "total_duration_sec": sum(s.get("duration_sec", round(target_duration_sec/len(scenes), 1)) for s in scenes),
            "character_seed": base_seed,
            "scenes": scenes,
        }
    except Exception as e:
        logger.warning(f"Gemini API call failed, falling back to heuristic engine: {e}")
        return None


def decompose_storyboard(
    script: str,
    target_duration_sec: float = 60.0,
    scene_count: int = 6,
    style: str = "cinematic",
    model: str = "gemini-3.7-flash",
    character_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Unified entrypoint: tries Gemini API first, seamlessly falls back to heuristic engine."""
    # Attempt Gemini API if key is present
    result = call_gemini_decompose_api(
        script=script,
        target_duration_sec=target_duration_sec,
        scene_count=scene_count,
        style=style,
        model=model,
    )
    if result:
        return result

    # Fallback to deterministic algorithmic cinematic decomposer
    return decompose_script_rule_based(
        script=script,
        target_duration_sec=target_duration_sec,
        scene_count=scene_count,
        style=style,
        character_seed=character_seed,
    )
