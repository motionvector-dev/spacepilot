import asyncio
import sys
import os
import logging
from pathlib import Path
import argparse
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

from .audio import AudioIO
from .live_client import GeminiLiveClient
from .wake_word import WakeWordDetector

# Setup dedicated on-call observability log
LOG_DIR = Path.home() / ".spacepilot" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "voice.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("space_voice")

console = Console()

class StatusUI:
    def __init__(self):
        self.status = "WAITING FOR 'SPACE' (WAKE WORD)..."

    def set_status(self, new_status: str):
        self.status = new_status

    def generate_renderable(self):
        color = "white"
        if "WAKE" in self.status:
            color = "cyan"
        elif self.status == "LIVE" or self.status == "LISTENING":
            color = "green"
        elif self.status == "SPEAKING":
            color = "magenta"
        elif self.status == "RUNNING_TOOL":
            color = "yellow"
        elif self.status == "ERROR":
            color = "red"
        
        text = Text(self.status, style=f"bold {color}", justify="center")
        return Panel(Align.center(text, vertical="middle"), title="SpacePilot Voice HUD", border_style=color, height=5)

async def main_async(enable_wake: bool = False):
    ui = StatusUI()
    if not enable_wake:
        ui.set_status("INITIALIZING...")
    
    def on_status_change(status: str):
        ui.set_status(status)

    audio_io = AudioIO()
    audio_io.start()

    client = GeminiLiveClient(audio_io, on_status_change=on_status_change)
    
    if enable_wake:
        wake_detector = WakeWordDetector(threshold=0.5)
        print("Listening for wake word...")

    
    with Live(ui.generate_renderable(), refresh_per_second=10, screen=True) as live:
        try:
            # We map status changes to a small async sleep loop to keep the UI responsive
            # while the actual IO happens in the background tasks.
            await client.connect()
            
            while client.running:
                live.update(ui.generate_renderable())
                await asyncio.sleep(0.1)
                
        except KeyboardInterrupt:
            pass
        except Exception as e:
            console.print(f"[red]Fatal Error: {e}[/red]")
        finally:
            await client.disconnect()
            audio_io.stop()

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
