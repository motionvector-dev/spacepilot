"""
On-device Wake Word Detection for SpacePilot Voice
==================================================
Runs locally using openWakeWord (ONNX Runtime) with near-zero CPU footprint.
Listens passively for the wake cue before opening the live Gemini WebSocket stream.
"""

import numpy as np
from openwakeword.model import Model
from typing import Optional, Callable

class WakeWordDetector:
    def __init__(self, threshold: float = 0.5, on_wake: Optional[Callable[[], None]] = None):
        self.threshold = threshold
        self.on_wake = on_wake or (lambda: None)
        # Load the local openWakeWord model
        self.model = Model(
            wakeword_models=["hey_jarvis_v0.1.onnx"],
            inference_framework="onnx"
        )
        self.active = True

    def process_chunk(self, audio_chunk_pcm: bytes) -> bool:
        """
        Processes a chunk of 16kHz, 16-bit mono PCM audio.
        Returns True if wake word was detected.
        """
        if not self.active:
            return False

        # Convert raw PCM bytes to 16-bit signed numpy array
        audio_data = np.frombuffer(audio_chunk_pcm, dtype=np.int16)
        
        # Predict wake word probability
        predictions = self.model.predict(audio_data)
        
        for name, score in predictions.items():
            if score >= self.threshold:
                # Trigger wake callback
                self.on_wake()
                return True
        return False
