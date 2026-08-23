import sys
import torch
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer

def enhance(prompt):
    model_id = "Qwen/Qwen2.5-1.5B-Instruct"
    
    # Load tokenizer and model onto Apple Silicon MPS
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, 
        torch_dtype=torch.float16, 
        device_map="mps"
    )

    system_prompt = """You are an expert cinematographer and prompt engineer for LTX-Video, an advanced AI video generation model.
Your task is to take a user's brief idea and expand it into a single, highly detailed, flowing paragraph (under 150 words).

Rules for LTX-Video prompts:
1. Start directly with the main action and subject.
2. Be explicit about spatial layout (foreground, background, left, right).
3. Specify camera angles and smooth camera movements (pan, tilt, dolly, zoom, tracking shot, close-up, wide shot).
4. Describe the lighting, atmosphere, and textures in rich detail (e.g., cinematic lighting, volumetric fog, photorealistic, 8k).
5. Describe the scene chronologically and avoid sudden cuts, scene changes, or text generation.
6. If the user provides a specific style, maintain it. Otherwise, default to high-quality, photorealistic cinematic style.

Output ONLY the final expanded prompt text. Do not include any conversational filler, titles, or quotes."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to("mps")
    
    generated_ids = model.generate(
        inputs.input_ids, 
        max_new_tokens=150, 
        do_sample=True, 
        temperature=0.7
    )
    
    generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, generated_ids)]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    return response.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, required=True)
    args = parser.parse_args()
    
    try:
        enhanced = enhance(args.prompt)
        print(enhanced)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
