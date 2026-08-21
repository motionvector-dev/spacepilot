---
name: pluto-video-director
description: Expert AI agent skill for directing and generating videos using Pluto Studio's MCP server.
---

# Pluto Video Director

This skill enables an AI agent to interact with Pluto Studio's MCP server to generate and manage video, audio, and music assets.

## Capabilities

* **Video Generation:** Use `pluto_generate_video` to create video clips.
* **Video Extension:** Use `pluto_extend_video` to continue existing video clips.
* **Audio Generation:** Use `pluto_generate_audio` (powered by Kokoro TTS) for voiceovers.
* **Music Generation:** Use `pluto_generate_music` for background tracks.
* **Status Checking:** Use `pluto_get_render_status` to monitor job progress and `pluto_get_fleet_status` to check GPU availability.

## Best Practices & Progressive Disclosure Guidance

### 3D Camera Trajectory & STG Guidance
* Use `camera_pan`, `camera_tilt`, and `camera_zoom` carefully to control camera motion.
* Adjust `camera_intensity` (1-10) to scale the motion effect.
* Tune STG (Spatio-Temporal Guidance) for better temporal consistency in complex motions.

### FLF2V Keyframe Morphing
* Follow strict FLF2V keyframe morphing rules when blending between initial and terminal frames. Ensure visual continuity and avoid abrupt subject changes unless desired.

### Kokoro TTS Audio Mixing
* Ensure audio is normalized to a standard LUFS level before mixing with video and music.
* Utilize the available voice catalogue (`pluto://voices/catalogue`) to pick the appropriate tone.

### Spot GPU Cost Budgeting
* **Draft Mode (`draft_mode=True`):** Use for rapid iteration and testing. Cost is approximately $0.012 per generation.
* **Cinema Mode (`draft_mode=False`):** Use for final, high-quality renders. Cost is approximately $0.040 per generation.
* Always poll `pluto_get_fleet_status()` to ensure resources are available before scheduling large batch jobs.
