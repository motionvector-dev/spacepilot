import asyncio
import time
import os
import psutil
import numpy as np
import wave
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_local_voice")

from spacepilot.drivers.local_voice_engine import LocalVoiceEngine

async def mock_audio_stream():
    rate = 16000
    duration = 2
    samples = np.random.normal(0, 0.1, rate * duration).astype(np.float32)
    samples_int16 = (samples * 32767).astype(np.int16)
    
    chunk_size = 4096
    for i in range(0, len(samples_int16), chunk_size):
        yield samples_int16[i:i+chunk_size].tobytes()
        await asyncio.sleep(0.01)

async def main():
    if not os.path.exists("kokoro-v1.0.onnx") or not os.path.exists("voices-v1.0.bin"):
        logger.error("Kokoro ONNX models not found in current directory. Please download them from:")
        logger.error("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx")
        logger.error("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin")
        return
        
    engine = LocalVoiceEngine(
        asr_model="tiny.en",
        llm_model="mlx-community/Qwen2.5-0.5B-Instruct-4bit",
        tts_model="kokoro-v1.0.onnx",
        voices_json="voices-v1.0.bin"
    )
    
    await engine.initialize()
    
    process = psutil.Process(os.getpid())
    
    t0 = time.time()
    
    audio_bytes = bytearray()
    async for chunk in mock_audio_stream():
        audio_bytes.extend(chunk)
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    t_asr_start = time.time()
    text = engine.transcribe(audio_np)
    t_asr_end = time.time()
    logger.info(f"ASR Text: {text}")
    
    t_llm_start = time.time()
    response = engine.generate_llm(text if text else "Hello SpacePilot! System check nominal.")
    t_llm_end = time.time()
    logger.info(f"LLM Response: {response}")
    
    t_tts_start = time.time()
    samples, sr = engine.synthesize_tts(response)
    t_tts_end = time.time()
    
    t_total = t_tts_end - t_asr_start
    
    mem_after = process.memory_info().rss / (1024 ** 3)
    
    print("\n--- PERFORMANCE METRICS ---")
    print(f"ASR Latency: {(t_asr_end - t_asr_start)*1000:.2f} ms")
    print(f"LLM TTFT / Total: {(t_llm_end - t_llm_start)*1000:.2f} ms")
    print(f"TTS Latency: {(t_tts_end - t_tts_start)*1000:.2f} ms")
    print(f"Total Pipeline Latency: {t_total*1000:.2f} ms")
    print(f"Resident Memory: {mem_after:.2f} GB")
    if len(samples) > 0:
        duration = len(samples) / sr
        rtf = (t_tts_end - t_tts_start) / duration
        print(f"TTS RTF: {rtf:.3f}")
    
    with wave.open("output.wav", "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((samples * 32767).astype(np.int16).tobytes())
        print("Saved generated audio to output.wav")

if __name__ == "__main__":
    asyncio.run(main())
