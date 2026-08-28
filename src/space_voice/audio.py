import asyncio
import sounddevice as sd
import numpy as np
import queue

class AudioIO:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, dtype: str = "int16"):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        
        # We use asyncio.Queue for async integration, but sounddevice callbacks run in a different thread.
        # So we use queue.Queue for the callback, and a background task to move items to asyncio.Queue
        self._input_queue_sync = queue.Queue()
        self._output_queue_sync = queue.Queue()
        
        self.input_queue = asyncio.Queue()
        
        self._in_stream = None
        self._out_stream = None
        self._running = False
        
    def _audio_callback(self, indata, outdata, frames, time, status):
        if status:
            pass # Handle or log underflows/overflows if necessary

        # Output logic
        try:
            chunk = self._output_queue_sync.get_nowait()
            # Ensure chunk size matches expected frames, pad if necessary
            if len(chunk) < frames:
                outdata[:len(chunk)] = chunk
                outdata[len(chunk):] = b'\x00' * ((frames - len(chunk)) * 2) # 2 bytes per sample for int16
            else:
                outdata[:] = chunk[:frames]
                # If there's leftover, we technically lose it in this simple impl, 
                # a proper circular buffer would keep the remainder.
        except queue.Empty:
            outdata.fill(0)
            
        # Input logic
        if indata is not None:
            self._input_queue_sync.put_nowait(bytes(indata))

    async def _queue_pump(self):
        while self._running:
            try:
                # Move from sync input queue to async input queue
                while not self._input_queue_sync.empty():
                    chunk = self._input_queue_sync.get_nowait()
                    await self.input_queue.put(chunk)
            except Exception:
                pass
            await asyncio.sleep(0.01)

    def play_audio(self, pcm_data: bytes):
        """Enqueue raw PCM data for playback."""
        # Convert raw bytes to numpy array for sounddevice
        arr = np.frombuffer(pcm_data, dtype=self.dtype).reshape(-1, self.channels)
        self._output_queue_sync.put_nowait(arr)

    def start(self):
        self._running = True
        self._stream = sd.Stream(
            samplerate=self.sample_rate,
            blocksize=2048,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._audio_callback
        )
        self._stream.start()
        self._pump_task = asyncio.create_task(self._queue_pump())

    def stop(self):
        self._running = False
        if hasattr(self, "_stream") and self._stream:
            self._stream.stop()
            self._stream.close()
        if hasattr(self, "_pump_task") and self._pump_task:
            self._pump_task.cancel()

    def clear_output_buffer(self):
        """Clear playback buffer (e.g., for barge-in)."""
        while not self._output_queue_sync.empty():
            try:
                self._output_queue_sync.get_nowait()
            except queue.Empty:
                break
