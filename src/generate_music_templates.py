"""Generate the studio's built-in BGM library from structured captions.

Reads assets/music_caption_refs/studio_bgm_captions.json, generates each cue
sequentially against the local MiniMax-Music3 mlx-serve server, then writes a
loudness-normalized master next to the raw take.

Usage: python src/generate_music_templates.py [--only id1,id2] [--force]
"""

import argparse
import json
import math
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PLUTO_ROOT = Path(__file__).resolve().parent.parent
CAPTIONS = PLUTO_ROOT / "assets" / "music_caption_refs" / "studio_bgm_captions.json"
MUSIC_DIR = PLUTO_ROOT / "outputs" / "music"
SERVER = "http://127.0.0.1:11234/v1/audio/music-generations"
MODEL = "ddalcu/MiniMax-Music3-MLX-Serve-8bit"
# Matches the studio loudness gate (-14 to -18 dBFS program loudness).
TARGET_LUFS = -16


def generate(cue: dict, out_raw: Path) -> None:
    body = json.dumps(
        {
            "model": MODEL,
            "prompt": cue["caption"],
            "lyrics": cue["lyrics"],
            "duration_seconds": cue["duration_seconds"],
            "seed": cue["seed"],
        }
    ).encode()
    req = urllib.request.Request(
        SERVER, data=body, headers={"Content-Type": "application/json"}
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=3600) as resp:
        audio = resp.read()
    out_raw.write_bytes(audio)
    print(f"  generated {len(audio) / 1e6:.1f} MB in {time.time() - start:.0f}s")


def normalize(out_raw: Path, out_norm: Path) -> None:
    """Two-pass loudnorm: the single-pass live estimator missed the target by
    1-4 LU in both directions on real cues. Pass 1 measures; pass 2 feeds the
    measurement back. Non-finite measurements (silence measures as -inf and
    makes ffmpeg fail) fall back to the single pass."""
    base = f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11"
    measure = subprocess.run(
        ["ffmpeg", "-i", str(out_raw), "-af", base + ":print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    try:
        m = json.loads(measure[measure.rindex("{"):measure.rindex("}") + 1])
        vals = {k: float(m[k]) for k in
                ("input_i", "input_tp", "input_lra", "input_thresh")}
        if not all(math.isfinite(v) for v in vals.values()):
            raise ValueError("non-finite loudness measurement")
        af = (f"{base}:measured_I={vals['input_i']}"
              f":measured_TP={vals['input_tp']}"
              f":measured_LRA={vals['input_lra']}"
              f":measured_thresh={vals['input_thresh']}:linear=true")
    except (ValueError, KeyError, json.JSONDecodeError):
        af = base
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(out_raw),
         "-af", af, "-ar", "44100", str(out_norm)],
        check=True,
    )


def measure(path: Path) -> str:
    probe = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    return " ".join(
        line.split("] ")[-1] for line in probe.splitlines() if "_volume" in line
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated cue ids")
    ap.add_argument("--force", action="store_true", help="regenerate existing")
    args = ap.parse_args()

    cues = json.loads(CAPTIONS.read_text())["cues"]
    if args.only:
        wanted = set(args.only.split(","))
        cues = [c for c in cues if c["id"] in wanted]
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    failed = []
    for cue in cues:
        raw = MUSIC_DIR / f"{cue['id']}_raw.wav"
        norm = MUSIC_DIR / f"{cue['id']}.wav"
        if norm.exists() and not args.force:
            print(f"[skip] {cue['id']} (exists)")
            continue
        print(f"[gen ] {cue['id']} ({cue['duration_seconds']}s, seed {cue['seed']})")
        try:
            generate(cue, raw)
            normalize(raw, norm)
            print(f"  normalized -> {norm.name}: {measure(norm)}")
        except (urllib.error.URLError, subprocess.CalledProcessError, OSError) as e:
            print(f"  FAILED: {e}", file=sys.stderr)
            failed.append(cue["id"])

    print(f"\ndone: {len(cues) - len(failed)}/{len(cues)} ok"
          + (f", failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
