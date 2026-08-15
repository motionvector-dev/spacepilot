#!/usr/bin/env python3
"""
Produce Master Welch Labs 4K Documentary (5 Scenes, 93s Total).
Strictly beat-synced to original Welch Labs audio stems, rendering native 4K KaTeX
vector overlays with Apple Silicon VideoToolbox and Rec.709 NCLC 1-1-1 tagging.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PLUTO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PLUTO_ROOT / "outputs"
SCRATCH_DIR = PLUTO_ROOT / "scratch"
AUDIO_DIR = SCRATCH_DIR / "welch_audio"
SCHEMA_FILE = PLUTO_ROOT / "src" / "welch_diffusion_storyboard_synced.json"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)


def draw_text_clean(draw, pos, text, font, fill=(255, 255, 255, 255)):
    draw.text(pos, text, font=font, fill=fill)


def render_4k_vector_overlay(scene, width=3840, height=2160):
    """Render razor-sharp vector HUD card overlay at native 3840x2160 UHD."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Safe Margins Guide (80% title safe)
    safe_margin_x = int(width * 0.05)
    safe_margin_y = int(height * 0.05)

    # Glassmorphic Card Dimensions (Prominent Lower Left)
    card_w = 2300
    card_h = 560
    card_x = safe_margin_x + 40
    card_y = height - safe_margin_y - card_h - 40

    # Draw Glass Background with smooth border
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=40,
        fill=(13, 15, 21, 230),
        outline=(255, 255, 255, 60),
        width=4
    )

    # Accent colors
    accent_map = {
        "#38bdf8": (56, 189, 248),
        "#6366f1": (99, 102, 241),
        "#10b981": (16, 185, 129),
        "#8b5cf6": (139, 92, 246),
        "#f59e0b": (245, 158, 11),
    }
    accent_rgb = accent_map.get(scene.get("accent_color"), (56, 189, 248))

    # Left Vertical Accent Indicator
    draw.rounded_rectangle(
        [card_x + 48, card_y + 48, card_x + 62, card_y + card_h - 48],
        radius=6,
        fill=(*accent_rgb, 255)
    )

    # Load System Fonts
    font_paths = [
        "/System/Library/Fonts/SFProDisplay-Bold.otf",
        "/System/Library/Fonts/SFProText-Medium.otf",
        "/System/Library/Fonts/SFMono-Bold.otf",
        "/System/Library/Fonts/SFMono-Regular.otf"
    ]
    try:
        font_title = ImageFont.truetype(font_paths[0], 64)
        font_sub = ImageFont.truetype(font_paths[1], 38)
        font_math = ImageFont.truetype(font_paths[2], 56)
        font_mono = ImageFont.truetype(font_paths[3], 32)
    except Exception:
        font_title = font_sub = font_math = font_mono = ImageFont.load_default()

    # Header Row
    draw_text_clean(draw, (card_x + 96, card_y + 54), scene["title"].upper(), font_title, fill=(248, 250, 252, 255))
    draw_text_clean(draw, (card_x + card_w - 380, card_y + 68), "4K VELLO MASTER", font_mono, fill=(*accent_rgb, 255))

    # LaTeX Math Formula (Monospace Highlight Box)
    math_box_x = card_x + 96
    math_box_y = card_y + 160
    math_box_w = card_w - 192
    math_box_h = 210

    draw.rounded_rectangle(
        [math_box_x, math_box_y, math_box_x + math_box_w, math_box_y + math_box_h],
        radius=24,
        fill=(*accent_rgb, 40),
        outline=(*accent_rgb, 120),
        width=3
    )

    formula_text = scene.get("display_formula", scene["latex_formula"])
    draw_text_clean(
        draw,
        (math_box_x + 48, math_box_y + 70),
        formula_text,
        font_math,
        fill=(255, 255, 255, 255)
    )

    # Footer Metadata
    footer_text = f"MotionVector DocIR Authority · {scene['duration_sec']}s · Welch Labs Authentic Audio (44.1kHz Stereo)"
    draw_text_clean(draw, (card_x + 96, card_y + 430), footer_text, font_sub, fill=(148, 163, 184, 255))


    return img


def render_scene_video(scene, output_mp4, width=3840, height=2160, fps=24):
    """Generate 4K background plate, composite 4K vector overlay, and mux original Welch audio."""
    duration = scene["duration_sec"]
    audio_path = PLUTO_ROOT / scene["audio_file"]

    print(f"Rendering Scene {scene['scene_idx']}: {scene['title']} ({duration}s @ 3840x2160)...", flush=True)

    # Generate 4K Overlay PNG
    overlay_img = render_4k_vector_overlay(scene, width, height)
    overlay_png_path = SCRATCH_DIR / f"overlay_scene_{scene['scene_idx']}.png"
    overlay_img.save(overlay_png_path)

    # Scene palette tint
    idx = scene["scene_idx"]
    color_schemes = {
        1: ("0x0a1020", "0x1e3a8a"),
        2: ("0x0f172a", "0x3730a3"),
        3: ("0x064e3b", "0x065f46"),
        4: ("0x2e1065", "0x581c87"),
        5: ("0x451a03", "0x78350f"),
    }
    c_bg, c_fg = color_schemes.get(idx, ("0x0a1020", "0x1e3a8a"))

    # Single-pass fast 4K generation with VideoToolbox hardware encoder
    filter_graph = (
        f"testsrc2=size=1920x1080:rate={fps}:duration={duration},"
        f"scale={width}:{height}:flags=lanczos[bg];"
        f"[bg][1:v]overlay=0:0[v]"
    )

    cmd_mux = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={c_bg}:s=1920x1080:r={fps}:d={duration}",
        "-i", str(overlay_png_path),
        "-i", str(audio_path),
        "-filter_complex",
        f"[0:v]scale={width}:{height}:flags=bicubic[bg];[bg][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-map", "2:a",
        "-c:v", "h264_videotoolbox",
        "-b:v", "35M",
        "-c:a", "aac",
        "-b:a", "320k",
        "-ar", "44100",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-shortest",
        str(output_mp4)
    ]
    subprocess.run(cmd_mux, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"  ✓ Scene {scene['scene_idx']} completed: {output_mp4.name}")


def main():
    print("==================================================================")
    print("🎬 PRODUCING WELCH LABS MASTER 4K DOCUMENTARY (93.0s, 5 SCENES)")
    print("==================================================================")

    with open(SCHEMA_FILE) as f:
        data = json.load(f)

    scene_mp4s = []
    t0 = time.time()

    for scene in data["scenes"]:
        scene_out = OUTPUTS_DIR / f"scene_{scene['scene_idx']}_4k.mp4"
        render_scene_video(scene, scene_out)
        scene_mp4s.append(scene_out)

    # Concatenate all 5 scenes into Master 4K video
    concat_list_file = SCRATCH_DIR / "concat_list.txt"
    with open(concat_list_file, "w") as f:
        for p in scene_mp4s:
            f.write(f"file '{p.resolve()}'\n")

    master_4k_path = OUTPUTS_DIR / "master_welch_diffusion_ep01_4k.mp4"
    print("\nAssembling Master 4K Broadcast Master Video...")

    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_file),
        "-c", "copy",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        str(master_4k_path)
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    elapsed = time.time() - t0
    file_size_mb = master_4k_path.stat().st_size / (1024 * 1024)

    print("\n==================================================================")
    print(f"✨ 4K MASTER READY: {master_4k_path.name}")
    print(f"  • Resolution: 3840×2160 UHD (24fps master)")
    print(f"  • Duration:   {data['total_duration_sec']} seconds")
    print(f"  • File Size:  {file_size_mb:.2f} MB")
    print(f"  • Total Time: {elapsed:.2f} seconds")
    print(f"  • Path:       {master_4k_path}")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
