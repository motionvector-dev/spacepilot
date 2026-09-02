import pytest
import asyncio
from space_voice.audio import AudioIO

@pytest.mark.asyncio
async def test_audio_io_queues():
    audio = AudioIO(sample_rate=16000, channels=1, dtype="int16")
    # We won't start the actual stream in CI, just test buffer clearing
    audio.play_audio(b'\x00' * 100)
    assert not audio._output_queue_sync.empty()
    
    audio.clear_output_buffer()
    assert audio._output_queue_sync.empty()
