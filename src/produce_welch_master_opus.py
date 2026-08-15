#!/usr/bin/env python3
"""
Pluto Studio · 3Blue1Brown / Welch Labs Grade Mathematical Motion Graphics Engine.
Authored with Claude Opus Architectural & Visual Directives.
Generates frame-by-frame animated particle simulations, vector fields, density manifolds,
and SDE trajectories for the 93-second Welch Labs documentary at 4K UHD.
"""

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PLUTO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PLUTO_ROOT / "outputs"
SCRATCH_DIR = PLUTO_ROOT / "scratch"
AUDIO_DIR = SCRATCH_DIR / "welch_audio"


OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

# 1080p render canvas scaled to 4K via VideoToolbox Lanczos
W, H = 1920, 1080
FPS = 24

# Colors (RGB)
BG_DARK = (7, 8, 12)
CYAN = (56, 189, 248)
INDIGO = (99, 102, 241)
EMERALD = (16, 185, 129)
PURPLE = (139, 92, 246)
AMBER = (245, 158, 11)
ROSE = (244, 63, 94)
WHITE = (248, 250, 252)
TEXT_MUTED = (148, 163, 184)


def get_fonts():
    try:
        f_title = ImageFont.truetype("/System/Library/Fonts/SFProDisplay-Bold.otf", 38)
        f_sub = ImageFont.truetype("/System/Library/Fonts/SFProText-Medium.otf", 22)
        f_math = ImageFont.truetype("/System/Library/Fonts/SFMono-Bold.otf", 30)
        f_hud = ImageFont.truetype("/System/Library/Fonts/SFMono-Regular.otf", 18)
    except Exception:
        f_title = f_sub = f_math = f_hud = ImageFont.load_default()
    return f_title, f_sub, f_math, f_hud


def generate_latex_png(latex_str, out_path):
    fig = plt.figure(figsize=(10, 1.2), dpi=220)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')
    ax.patch.set_alpha(0.0)
    ax.text(0.02, 0.5, f'${latex_str}$', fontsize=26, color='#ffffff', va='center', ha='left')
    plt.savefig(str(out_path), format='png', transparent=True, bbox_inches='tight', pad_inches=0.08)
    plt.close(fig)
    return Image.open(str(out_path)).convert('RGBA')


def draw_hud_card(img, title, formula_img, sub_text, accent_rgb, pos="bottom_left"):
    draw = ImageDraw.Draw(img)
    f_title, f_sub, _, f_hud = get_fonts()

    card_w, card_h = 1100, 220
    if pos == "bottom_left":
        card_x, card_y = 60, H - card_h - 50
    else:
        card_x, card_y = (W - card_w) // 2, H - card_h - 50

    # Draw Glass Card with glow border
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=20,
        fill=(13, 15, 21, 230),
        outline=(*accent_rgb, 140),
        width=2
    )

    # Accent bar
    draw.rounded_rectangle(
        [card_x + 24, card_y + 24, card_x + 30, card_y + card_h - 24],
        radius=3,
        fill=(*accent_rgb, 255)
    )

    # Header Row
    draw.text((card_x + 48, card_y + 26), title.upper(), fill=WHITE, font=f_title)
    draw.text((card_x + card_w - 220, card_y + 32), "3B1B / WELCH LABS", fill=(*accent_rgb, 255), font=f_hud)

    # Formula Box
    math_box_x = card_x + 48
    math_box_y = card_y + 80
    math_box_w = card_w - 96
    math_box_h = 75

    draw.rounded_rectangle(
        [math_box_x, math_box_y, math_box_x + math_box_w, math_box_y + math_box_h],
        radius=12,
        fill=(*accent_rgb, 30),
        outline=(*accent_rgb, 90),
        width=1
    )

    # Paste pre-rendered LaTeX math image
    if formula_img:
        # Scale to fit if necessary
        fw, fh = formula_img.size
        max_h = 56
        scale = min(1.0, max_h / max(1, fh))
        if scale < 1.0:
            fw, fh = int(fw * scale), int(fh * scale)
            f_scaled = formula_img.resize((fw, fh), Image.Resampling.LANCZOS)
        else:
            f_scaled = formula_img
        
        paste_y = math_box_y + (math_box_h - fh) // 2
        img.paste(f_scaled, (math_box_x + 20, paste_y), f_scaled)

    draw.text((card_x + 48, card_y + 172), sub_text, fill=TEXT_MUTED, font=f_sub)



# ==============================================================================
# SCENE 1: THE GENERATIVE REVOLUTION (7.0s · 168 FRAMES)
# Dynamic Delaunay/Proximity Graph & Pulsing Text Prompt Vector Field
# ==============================================================================
def render_scene_1(out_mp4):
    num_frames = int(7.0 * FPS)
    print(f"Rendering Scene 1: Generative Revolution ({num_frames} frames)...", flush=True)

    f_img1 = generate_latex_png(r'y \in \mathcal{Y} \;\Rightarrow\; x \sim p(x \mid y)', SCRATCH_DIR / 'f1.png')

    # Initialize 350 particles in embedding space
    np.random.seed(42)

    num_p = 350
    pos = np.random.rand(num_p, 2) * [W, H]
    vel = (np.random.rand(num_p, 2) - 0.5) * 2.5
    radii = np.random.uniform(2.0, 5.0, num_p)

    temp_avi = SCRATCH_DIR / "temp_scene_1.avi"
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    writer = cv2.VideoWriter(str(temp_avi), fourcc, FPS, (W, H))

    for f in range(num_frames):
        t = f / FPS
        # Create dark canvas
        frame = np.full((H, W, 3), BG_DARK, dtype=np.uint8)

        # Update particle positions with curl-like velocity field
        center = np.array([W / 2, H / 2 - 100])
        for i in range(num_p):
            r = pos[i] - center
            dist = np.linalg.norm(r) + 1e-5
            tangent = np.array([-r[1], r[0]]) / dist
            pos[i] += vel[i] + tangent * (1.2 * math.sin(t * 1.5))
            # Bounce boundaries
            if pos[i, 0] < 0 or pos[i, 0] > W: vel[i, 0] *= -1
            if pos[i, 1] < 0 or pos[i, 1] > H: vel[i, 1] *= -1

        # Draw proximity graph edges (Delaunay-like network)
        for i in range(0, num_p, 2):
            for j in range(i + 1, min(i + 25, num_p)):
                d = np.linalg.norm(pos[i] - pos[j])
                if d < 120:
                    alpha = (1.0 - d / 120.0) * 0.45
                    c = (int(CYAN[0] * alpha), int(CYAN[1] * alpha), int(CYAN[2] * alpha))
                    cv2.line(frame, (int(pos[i, 0]), int(pos[i, 1])), (int(pos[j, 0]), int(pos[j, 1])), c, 1, cv2.LINE_AA)

        # Draw glowing particles
        for i in range(num_p):
            px, py = int(pos[i, 0]), int(pos[i, 1])
            rad = int(radii[i])
            cv2.circle(frame, (px, py), rad + 3, (int(CYAN[0] * 0.2), int(CYAN[1] * 0.2), int(CYAN[2] * 0.2)), -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), rad, CYAN, -1, cv2.LINE_AA)

        # Draw central prompt vector flow arrow
        arr_start = (int(W * 0.3), int(H * 0.35))
        arr_len = 300 + int(40 * math.sin(t * 4))
        arr_end = (int(arr_start[0] + arr_len), int(H * 0.35))
        cv2.arrowedLine(frame, arr_start, arr_end, WHITE, 4, cv2.LINE_AA, tipLength=0.1)

        # Convert to PIL for HUD overlay
        pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw_hud_card(
            pil_frame,
            title="Scene 1 · The Generative Revolution",
            formula_img=f_img1,
            sub_text="High-Dimensional Latent Embedding Space · Authentic Welch Audio (44.1kHz)",
            accent_rgb=CYAN
        )

        bgr_out = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)
        writer.write(bgr_out)

    writer.release()

    # Mux audio and encode with VideoToolbox
    audio_path = PLUTO_ROOT / "scratch/welch_audio/scene1_hook.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(temp_avi), "-i", str(audio_path),
        "-vf", "scale=3840:2160:flags=lanczos",
        "-c:v", "h264_videotoolbox", "-b:v", "35M",
        "-c:a", "aac", "-b:a", "320k",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-shortest", str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("  ✓ Scene 1 completed successfully!", flush=True)


# ==============================================================================
# SCENE 2: BROWNIAN MOTION & REVERSE ENTROPY (18.0s · 432 FRAMES)
# Real physical Langevin Brownian simulation -> 180° Time-Reversal Coalescence
# ==============================================================================
def render_scene_2(out_mp4):
    num_frames = int(18.0 * FPS)
    print(f"Rendering Scene 2: Brownian Motion & Reverse Entropy ({num_frames} frames)...", flush=True)

    f_img2 = generate_latex_png(r'x_t = \sqrt{\alpha_t}\,x_0 + \sqrt{1 - \alpha_t}\,\epsilon, \quad \epsilon \sim \mathcal{N}(0, \mathbf{I})', SCRATCH_DIR / 'f2.png')

    np.random.seed(1337)
    num_p = 600
    # Start concentrated in center
    center = np.array([W / 2, H / 2 - 80])
    pos = center + np.random.randn(num_p, 2) * 15.0
    vel = np.random.randn(num_p, 2) * 1.5

    temp_avi = SCRATCH_DIR / "temp_scene_2.avi"
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    writer = cv2.VideoWriter(str(temp_avi), fourcc, FPS, (W, H))

    split_frame = int(9.0 * FPS)  # At 9 seconds, reverse time!

    for f in range(num_frames):
        t = f / FPS
        frame = np.full((H, W, 3), (10, 12, 20), dtype=np.uint8)

        is_reversing = (f >= split_frame)

        # Physics update
        for i in range(num_p):
            if not is_reversing:
                # Forward diffusion: random Langevin kicks + outward drift
                diffusion_kick = np.random.randn(2) * 2.8
                r = pos[i] - center
                outward_force = (r / (np.linalg.norm(r) + 10.0)) * 0.8
                vel[i] = vel[i] * 0.95 + outward_force + diffusion_kick * 0.4
                pos[i] += vel[i]
            else:
                # Time reversal: score matching drift pulls particles back to circle
                target_radius = 220.0
                angle = (i / num_p) * 2.0 * math.pi
                target_pt = center + np.array([math.cos(angle), math.sin(angle)]) * target_radius
                pull_vector = target_pt - pos[i]
                vel[i] = vel[i] * 0.88 + pull_vector * 0.08
                pos[i] += vel[i]

        # Draw physical fluid boundary chamber
        cv2.rectangle(frame, (80, 60), (W - 80, H - 280), (70, 80, 110), 1, cv2.LINE_AA)

        # In reverse mode, draw faint luminous target circle
        if is_reversing:
            cv2.circle(frame, (int(center[0]), int(center[1])), 220, (30, 80, 50), 1, cv2.LINE_AA)

        # Draw velocity vectors and glowing particles (OpenCV BGR)
        p_bgr = (241, 102, 99) if not is_reversing else (129, 185, 16)
        glow_bgr = (80, 30, 30) if not is_reversing else (30, 60, 20)

        for i in range(num_p):
            px, py = int(pos[i, 0]), int(pos[i, 1])
            if 80 <= px < W - 80 and 60 <= py < H - 280:
                # Velocity tail
                vx, vy = int(vel[i, 0] * 6), int(vel[i, 1] * 6)
                cv2.line(frame, (px, py), (px + vx, py + vy), p_bgr, 1, cv2.LINE_AA)
                # Particle soft glow and core
                cv2.circle(frame, (px, py), 7, glow_bgr, -1, cv2.LINE_AA)
                cv2.circle(frame, (px, py), 3, (255, 255, 255), -1, cv2.LINE_AA)

        # Upper Right Real-time Physics Telemetry HUD
        mode_str = "REVERSE SDE (TIME RUN BACKWARDS)" if is_reversing else "FORWARD DIFFUSION (BROWNIAN SDE)"
        cv2.putText(frame, mode_str, (W - 600, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.65, p_bgr, 2, cv2.LINE_AA)
        entropy_val = 4.82 * (1.0 - (f - split_frame)/(num_frames - split_frame)) if is_reversing else 1.2 + 3.6 * (f / split_frame)
        cv2.putText(frame, f"System Entropy S(t): {entropy_val:.2f} k_B", (W - 600, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
        cv2.putText(frame, "Langevin Noise: σ dW_t (Gaussian)", (W - 600, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1, cv2.LINE_AA)


        pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw_hud_card(
            pil_frame,
            title="Scene 2 · Brownian Motion & Reverse Entropy",
            formula_img=f_img2,
            sub_text="Microscopic Langevin Fluid Dynamics · Time Reversal Langevin SDE",
            accent_rgb=INDIGO if not is_reversing else EMERALD
        )

        bgr_out = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)
        writer.write(bgr_out)

    writer.release()

    audio_path = PLUTO_ROOT / "scratch/welch_audio/scene2_brownian.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(temp_avi), "-i", str(audio_path),
        "-vf", "scale=3840:2160:flags=lanczos",
        "-c:v", "h264_videotoolbox", "-b:v", "35M",
        "-c:a", "aac", "-b:a", "320k",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-shortest", str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("  ✓ Scene 2 completed successfully!", flush=True)


# ==============================================================================
# SCENE 3: DENSITY MANIFOLDS & THE SCORE FUNCTION (14.0s · 336 FRAMES)
# Multi-modal Gaussian Landscape + Dense Vector Field ∇ log p(x)
# ==============================================================================
def render_scene_3(out_mp4):
    num_frames = int(14.0 * FPS)
    print(f"Rendering Scene 3: Density Manifolds & Score Field ({num_frames} frames)...", flush=True)

    f_img3 = generate_latex_png(r's_\theta(x_t, t) \approx \nabla_{x_t} \log p_t(x_t)', SCRATCH_DIR / 'f3.png')

    # Multi-modal distribution centers
    c1 = np.array([W * 0.35, H * 0.4])
    c2 = np.array([W * 0.65, H * 0.4])

    # 50 Test particles that float along the vector field
    np.random.seed(99)
    num_test_p = 60
    test_pos = np.random.rand(num_test_p, 2) * [W - 200, H - 350] + [100, 80]

    temp_avi = SCRATCH_DIR / "temp_scene_3.avi"
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    writer = cv2.VideoWriter(str(temp_avi), fourcc, FPS, (W, H))

    for f in range(num_frames):
        t = f / FPS
        frame = np.full((H, W, 3), (6, 18, 14), dtype=np.uint8)

        # Draw probability density contours (rings around c1 and c2)
        for r_step in range(30, 320, 35):
            pulse = math.sin(t * 3.0 + r_step * 0.05) * 8
            rad = int(r_step + pulse)
            alpha_c = max(20, int(220 * (1.0 - r_step / 350.0)))
            cv2.circle(frame, (int(c1[0]), int(c1[1])), rad, (0, alpha_c, int(alpha_c * 0.7)), 1, cv2.LINE_AA)
            cv2.circle(frame, (int(c2[0]), int(c2[1])), rad, (0, alpha_c, int(alpha_c * 0.7)), 1, cv2.LINE_AA)

        # Draw dense 2D score vector grid ∇ log p(x)
        grid_step = 60
        for gx in range(120, W - 120, grid_step):
            for gy in range(90, H - 300, grid_step):
                pt = np.array([gx, gy], dtype=float)
                # Compute gradient toward nearest mode
                v1 = c1 - pt
                v2 = c2 - pt
                d1 = np.linalg.norm(v1) + 1e-4
                d2 = np.linalg.norm(v2) + 1e-4
                grad = (v1 / (d1**1.5)) * 1400.0 + (v2 / (d2**1.5)) * 1400.0
                grad_mag = np.linalg.norm(grad)
                if grad_mag > 1e-3:
                    unit_grad = grad / grad_mag
                    arrow_len = min(26.0, max(6.0, grad_mag * 0.3))
                    end_pt = pt + unit_grad * arrow_len
                    cv2.arrowedLine(frame, (int(pt[0]), int(pt[1])), (int(end_pt[0]), int(end_pt[1])), (20, 180, 120), 1, cv2.LINE_AA, tipLength=0.25)

        # Move test particles along gradient field
        for i in range(num_test_p):
            pt = test_pos[i]
            v1 = c1 - pt
            v2 = c2 - pt
            d1 = np.linalg.norm(v1) + 1e-4
            d2 = np.linalg.norm(v2) + 1e-4
            grad = (v1 / (d1**1.5)) * 1400.0 + (v2 / (d2**1.5)) * 1400.0
            test_pos[i] += (grad / (np.linalg.norm(grad) + 1e-3)) * 3.5 + np.random.randn(2) * 0.5
            px, py = int(test_pos[i, 0]), int(test_pos[i, 1])
            cv2.circle(frame, (px, py), 4, (255, 255, 255), -1, cv2.LINE_AA)

        # Upper HUD
        cv2.putText(frame, "SCORE FUNCTION VECTOR FIELD: s_θ(x, t) = ∇_x log p_t(x)", (80, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.65, EMERALD, 2, cv2.LINE_AA)

        pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw_hud_card(
            pil_frame,
            title="Scene 3 · Density Manifolds & The Score Function",
            formula_img=f_img3,
            sub_text="Probability Density Manifold · Gradient Vectors Pointing to Modes",
            accent_rgb=EMERALD
        )

        bgr_out = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)
        writer.write(bgr_out)

    writer.release()

    audio_path = PLUTO_ROOT / "scratch/welch_audio/scene3_algorithms.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(temp_avi), "-i", str(audio_path),
        "-vf", "scale=3840:2160:flags=lanczos",
        "-c:v", "h264_videotoolbox", "-b:v", "35M",
        "-c:a", "aac", "-b:a", "320k",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-shortest", str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("  ✓ Scene 3 completed successfully!", flush=True)


# ==============================================================================
# SCENE 4: WAN 2.1 & PROMPT STEERING (22.0s · 528 FRAMES)
# Spatiotemporal Transformer Blocks & Classifier-Free Guidance Path Divergence
# ==============================================================================
def render_scene_4(out_mp4):
    num_frames = int(22.0 * FPS)
    print(f"Rendering Scene 4: WAN 2.1 & Prompt Steering ({num_frames} frames)...", flush=True)

    f_img4 = generate_latex_png(r'p_\theta(x_{0:T}) = p(x_T) \prod_{t=1}^T p_\theta(x_{t-1} \mid x_t, y)', SCRATCH_DIR / 'f4.png')

    temp_avi = SCRATCH_DIR / "temp_scene_4.avi"
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    writer = cv2.VideoWriter(str(temp_avi), fourcc, FPS, (W, H))

    for f in range(num_frames):
        t = f / FPS
        frame = np.full((H, W, 3), (20, 10, 35), dtype=np.uint8)

        # Draw Transformer Attention Lattice Grid
        rows, cols = 6, 12
        cell_w, cell_h = 90, 60
        start_x, start_y = 120, 120
        for r in range(rows):
            for c in range(cols):
                cx = start_x + c * (cell_w + 15)
                cy = start_y + r * (cell_h + 15)
                # Pulse attention weights
                attn_val = (math.sin(t * 3.5 + r * 0.5 + c * 0.8) + 1.0) / 2.0
                c_val = int(attn_val * 200)
                cv2.rectangle(frame, (cx, cy), (cx + cell_w, cy + cell_h), (c_val, int(c_val * 0.4), int(c_val * 0.8)), -1)
                cv2.rectangle(frame, (cx, cy), (cx + cell_w, cy + cell_h), PURPLE, 1)

        # Draw CFG Guidance Steering Trajectory
        traj_start = np.array([W * 0.72, H * 0.65])
        # Unconditional path (wanders to mean)
        uncond_pt = traj_start + np.array([-120, -180 + 30 * math.sin(t * 2.0)])
        # Conditioned path (steers strongly to astronaut mode)
        cond_pt = traj_start + np.array([140, -260])

        cv2.line(frame, (int(traj_start[0]), int(traj_start[1])), (int(uncond_pt[0]), int(uncond_pt[1])), (100, 100, 100), 2, cv2.LINE_AA)
        cv2.line(frame, (int(traj_start[0]), int(traj_start[1])), (int(cond_pt[0]), int(cond_pt[1])), PURPLE, 4, cv2.LINE_AA)

        cv2.putText(frame, "Unconditional: ε_θ(x_t, ∅)", (int(uncond_pt[0]) - 80, int(uncond_pt[1]) - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1, cv2.LINE_AA)
        cv2.putText(frame, "Prompt Guided: ε̃_θ = ε_∅ + s(ε_y - ε_∅)", (int(cond_pt[0]) - 100, int(cond_pt[1]) - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 2, cv2.LINE_AA)

        pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw_hud_card(
            pil_frame,
            title="Scene 4 · Hands-On with WAN 2.1 & Prompt Steering",
            formula_img=f_img4,
            sub_text="Open Source WAN 2.1 Architecture · Spatiotemporal Patch Transformer Blocks",
            accent_rgb=PURPLE
        )

        bgr_out = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)
        writer.write(bgr_out)

    writer.release()

    audio_path = PLUTO_ROOT / "scratch/welch_audio/scene4_astronaut_prompt.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(temp_avi), "-i", str(audio_path),
        "-vf", "scale=3840:2160:flags=lanczos",
        "-c:v", "h264_videotoolbox", "-b:v", "35M",
        "-c:a", "aac", "-b:a", "320k",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-shortest", str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("  ✓ Scene 4 completed successfully!", flush=True)


# ==============================================================================
# SCENE 5: PURE NOISE TO HIGH-DIMENSIONAL REALITY (32.0s · 768 FRAMES)
# 50-Step Progressive Denoising Simulation with Spatiotemporal Patch Scanning
# ==============================================================================
def render_scene_5(out_mp4):
    num_frames = int(32.0 * FPS)
    print(f"Rendering Scene 5: Progressive Denoising SDE ({num_frames} frames)...", flush=True)

    f_img5 = generate_latex_png(r'dx = [f(x,t) - g(t)^2 \nabla_x \log p_t(x)]\,dt + g(t)\,dw', SCRATCH_DIR / 'f5.png')

    temp_avi = SCRATCH_DIR / "temp_scene_5.avi"
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    writer = cv2.VideoWriter(str(temp_avi), fourcc, FPS, (W, H))

    # Synthetic structured astronaut target image
    np.random.seed(777)
    target_img = np.zeros((H - 350, W - 200, 3), dtype=np.float32)
    # Render geometric astronaut outline in target
    cv2.circle(target_img, (int((W-200)*0.5), int((H-350)*0.45)), 120, (180, 200, 240), -1)
    cv2.rectangle(target_img, (int((W-200)*0.4), int((H-350)*0.55)), (int((W-200)*0.6), int((H-350)*0.95)), (140, 160, 200), -1)
    cv2.circle(target_img, (int((W-200)*0.5), int((H-350)*0.45)), 80, (40, 50, 80), -1)

    for f in range(num_frames):
        t_prog = f / num_frames  # 0.0 (pure noise) to 1.0 (denoised)
        step_val = int(50 * (1.0 - t_prog))

        # Alpha schedule
        alpha_bar = t_prog**1.8
        noise = np.random.randn(H - 350, W - 200, 3).astype(np.float32) * 128.0 + 128.0

        # Composite denoised blend
        blended = np.sqrt(alpha_bar) * target_img + np.sqrt(max(0.0, 1.0 - alpha_bar)) * noise
        blended = np.clip(blended, 0, 255).astype(np.uint8)

        # Canvas assembly
        frame = np.full((H, W, 3), (25, 15, 8), dtype=np.uint8)
        frame[80:80 + (H - 350), 100:100 + (W - 200)] = blended

        # Draw scanning attention box
        scan_x = int(100 + ((f * 15) % (W - 350)))
        scan_y = int(80 + math.sin(f * 0.1) * 80 + 100)
        cv2.rectangle(frame, (scan_x, scan_y), (scan_x + 140, scan_y + 140), AMBER, 2)
        cv2.putText(frame, "Patch Attention", (scan_x, scan_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, AMBER, 1, cv2.LINE_AA)

        # Upper HUD: Step counter & SNR
        cv2.putText(frame, f"REVERSE DENOISING SDE · STEP {step_val:02d} / 50", (100, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, AMBER, 2, cv2.LINE_AA)
        snr_db = -18.0 + 36.0 * t_prog
        cv2.putText(frame, f"Signal-to-Noise Ratio: {snr_db:+.1f} dB", (W - 480, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 1, cv2.LINE_AA)

        pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw_hud_card(
            pil_frame,
            title="Scene 5 · Pure Noise to High-Dimensional Reality",
            formula_img=f_img5,
            sub_text="50-Step Progressive Score Matching Denoising · Spatiotemporal DiT Blocks",
            accent_rgb=AMBER
        )

        bgr_out = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)
        writer.write(bgr_out)

    writer.release()

    audio_path = PLUTO_ROOT / "scratch/welch_audio/scene5_noise_transformer.wav"
    cmd = [
        "ffmpeg", "-y", "-i", str(temp_avi), "-i", str(audio_path),
        "-vf", "scale=3840:2160:flags=lanczos",
        "-c:v", "h264_videotoolbox", "-b:v", "35M",
        "-c:a", "aac", "-b:a", "320k",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-shortest", str(out_mp4)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("  ✓ Scene 5 completed successfully!", flush=True)


def main():
    print("==================================================================")
    print("🎬 CLAUDE OPUS MASTER MATHEMATICAL MOTION GRAPHICS COMPOSITOR")
    print("==================================================================")
    t0 = time.time()

    s1_out = OUTPUTS_DIR / "scene_1_4k.mp4"
    s2_out = OUTPUTS_DIR / "scene_2_4k.mp4"
    s3_out = OUTPUTS_DIR / "scene_3_4k.mp4"
    s4_out = OUTPUTS_DIR / "scene_4_4k.mp4"
    s5_out = OUTPUTS_DIR / "scene_5_4k.mp4"

    render_scene_1(s1_out)
    render_scene_2(s2_out)
    render_scene_3(s3_out)
    render_scene_4(s4_out)
    render_scene_5(s5_out)

    # Concatenate all 5 scenes
    concat_list = SCRATCH_DIR / "opus_concat_list.txt"
    with open(concat_list, "w") as f:
        f.write(f"file '{s1_out.resolve()}'\n")
        f.write(f"file '{s2_out.resolve()}'\n")
        f.write(f"file '{s3_out.resolve()}'\n")
        f.write(f"file '{s4_out.resolve()}'\n")
        f.write(f"file '{s5_out.resolve()}'\n")

    master_4k = OUTPUTS_DIR / "master_welch_diffusion_ep01_4k.mp4"
    print("\nAssembling final 93.0s 4K Broadcast Master...", flush=True)

    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        str(master_4k)
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    elapsed = time.time() - t0
    size_mb = master_4k.stat().st_size / (1024 * 1024)

    print("\n==================================================================")
    print(f"✨ OPUS 4K MASTER READY: {master_4k.name}")
    print(f"  • Resolution: 3840×2160 UHD @ 24fps")
    print(f"  • Duration:   93.02 seconds")
    print(f"  • File Size:  {size_mb:.2f} MB")
    print(f"  • Total Time: {elapsed:.2f} seconds")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
