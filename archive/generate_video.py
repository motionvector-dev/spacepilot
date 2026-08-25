#!/usr/bin/env python3
"""
LTX-Video Local Generation Script for macOS (Apple Silicon + MPS)
----------------------------------------------------------------
This script allows running local LTX-Video (or LTX-Video-distilled) inference
on Apple Silicon Macs using PyTorch's Metal Performance Shaders (MPS) backend.

It automatically handles:
1. Model loading (Text-to-Video and Image-to-Video).
2. Video dimension constraints (dimensions must be multiples of 32).
3. Frame count constraints (number of frames must be 8k + 1).
4. Local video export using diffusers' built-in tools.
"""

import argparse
import sys
import os
import time
import torch

from diffusers import LTXPipeline, LTXImageToVideoPipeline
from diffusers.utils import export_to_video, load_image


def adjust_frame_count(num_frames: int) -> int:
    """
    Adjusts the frame count to satisfy the LTX-Video requirement of (8 * k + 1).
    Rounds to the nearest valid value (minimum of 9).
    """
    if (num_frames - 1) % 8 == 0:
        return num_frames
    
    k = round((num_frames - 1) / 8)
    adjusted = (8 * k) + 1
    if adjusted < 9:
        adjusted = 9
        
    print(f"[Info] Adjusted frame count from {num_frames} to {adjusted} to satisfy LTX-Video (8*k + 1) constraints.")
    return adjusted


def adjust_dimension(dimension: int, name: str) -> int:
    """
    Adjusts a spatial dimension (width or height) to be a multiple of 32.
    Rounds to the nearest multiple (minimum of 32).
    """
    if dimension % 32 == 0:
        return dimension
        
    adjusted = round(dimension / 32) * 32
    if adjusted < 32:
        adjusted = 32
        
    print(f"[Info] Adjusted {name} from {dimension} to {adjusted} to satisfy LTX-Video multiples of 32 constraints.")
    return adjusted


def main():
    parser = argparse.ArgumentParser(description="Generate videos locally using LTX-Video on Apple Silicon.")
    
    # Main generation parameters
    parser.add_argument("--prompt", type=str, required=True, help="Text description of the video to generate.")
    parser.add_argument("--image", type=str, default=None, help="Path to input image for image-to-video generation.")
    parser.add_argument("--output", type=str, default="output.mp4", help="Path where the generated MP4 file will be saved.")
    
    # Model parameters
    parser.add_argument(
        "--model", 
        type=str, 
        default="Lightricks/LTX-Video-0.9.8-13B-distilled", 
        help="Hugging Face model repository ID or path to local checkpoints."
    )
    parser.add_argument(
        "--revision",
        type=str,
        default=None,
        help="Commit SHA or immutable tag to pin --model to. Without it the "
             "download follows the repo's default branch, so the same command "
             "can render from different weights on different days and nothing "
             "in the output says which it used."
    )
    
    # Generation configuration
    parser.add_argument("--width", type=int, default=512, help="Width of the output video. Must be a multiple of 32.")
    parser.add_argument("--height", type=int, default=288, help="Height of the output video. Must be a multiple of 32.")
    parser.add_argument("--num_frames", type=int, default=49, help="Number of frames. Must be of form 8k + 1 (e.g. 17, 25, 33, 41, 49).")
    parser.add_argument("--steps", type=int, default=25, help="Number of inference steps (distilled models work well with 20-30).")
    parser.add_argument("--guidance_scale", type=float, default=3.0, help="Classifier-free guidance scale (default: 3.0).")
    parser.add_argument("--fps", type=int, default=16, help="Frames per second of the exported video (default: 16).")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for generation.")
    
    # Optimization switches
    parser.add_argument("--enable_cpu_offload", action="store_true", help="Enable sequential CPU offloading to save memory (slows down generation).")
    
    args = parser.parse_args()

    # Verify MPS availability
    if not torch.backends.mps.is_available():
        print("[Warning] Apple Silicon MPS (Metal Performance Shaders) backend not found. Falling back to CPU.", file=sys.stderr)
        device = "cpu"
    else:
        device = "mps"
        print("[Info] Apple Silicon MPS backend detected. Using MPS for generation.")
        
    # Check and adjust constraints
    width = adjust_dimension(args.width, "width")
    height = adjust_dimension(args.height, "height")
    num_frames = adjust_frame_count(args.num_frames)

    # Determine seed/generator
    if args.seed is not None:
        generator = torch.Generator(device="cpu").manual_seed(args.seed)
    else:
        generator = None

    start_time = time.time()
    
    # Load model and set up pipeline
    if args.image:
        print(f"[Info] Loading Image-to-Video pipeline for model: {args.model}")
        if not os.path.exists(args.image) and not args.image.startswith("http"):
            print(f"[Error] Image path not found: {args.image}", file=sys.stderr)
            sys.exit(1)
            
        print(f"[Info] Loading source image from: {args.image}")
        source_image = load_image(args.image)
        
        # Load pipeline
        pipeline = LTXImageToVideoPipeline.from_pretrained(
            args.model,
            revision=args.revision,
            torch_dtype=torch.bfloat16
        )
    else:
        print(f"[Info] Loading Text-to-Video pipeline for model: {args.model}")
        source_image = None
        
        # Load pipeline
        pipeline = LTXPipeline.from_pretrained(
            args.model,
            revision=args.revision,
            torch_dtype=torch.bfloat16
        )

    # Apply optimizations or send to device
    if args.enable_cpu_offload:
        print("[Info] Enabling CPU offloading optimization.")
        pipeline.enable_model_cpu_offload()
    else:
        print(f"[Info] Loading entire pipeline into memory and moving to {device}...")
        pipeline.to(device)
        
    load_duration = time.time() - start_time
    print(f"[Success] Pipeline loaded in {load_duration:.2f} seconds.")
    
    # Run generation
    print("[Info] Starting video generation (this will take a while on local hardware)...")
    generation_start = time.time()
    
    try:
        if source_image is not None:
            # Image to video pipeline
            output = pipeline(
                image=source_image,
                prompt=args.prompt,
                width=width,
                height=height,
                num_frames=num_frames,
                num_inference_steps=args.steps,
                guidance_scale=args.guidance_scale,
                generator=generator,
            )
        else:
            # Text to video pipeline
            output = pipeline(
                prompt=args.prompt,
                width=width,
                height=height,
                num_frames=num_frames,
                num_inference_steps=args.steps,
                guidance_scale=args.guidance_scale,
                generator=generator,
            )
            
        video_frames = output.frames[0]
        gen_duration = time.time() - generation_start
        print(f"[Success] Video generation finished in {gen_duration:.2f} seconds.")
        
        # Export video
        print(f"[Info] Exporting video to {args.output}...")
        export_to_video(video_frames, args.output, fps=args.fps)
        print(f"[Success] Video successfully exported to: {args.output}")
        
    except Exception as e:
        print(f"[Error] Generation failed: {str(e)}", file=sys.stderr)
        raise e


if __name__ == "__main__":
    main()
