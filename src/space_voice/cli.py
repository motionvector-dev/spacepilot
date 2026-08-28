import asyncio
import sys
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.align import Align
from rich.text import Text

from .audio import AudioIO
from .live_client import GeminiLiveClient

console = Console()

class StatusUI:
    def __init__(self):
        self.status = "INITIALIZING..."

    def set_status(self, new_status: str):
        self.status = new_status

    def generate_renderable(self):
        color = "white"
        if self.status == "LIVE":
            color = "green"
        elif self.status == "LISTENING":
            color = "blue"
        elif self.status == "SPEAKING":
            color = "magenta"
        elif self.status == "RUNNING_TOOL":
            color = "yellow"
        elif self.status == "ERROR":
            color = "red"
        
        text = Text(self.status, style=f"bold {color}", justify="center")
        return Panel(Align.center(text, vertical="middle"), title="VoicePilot HUD", border_style=color, height=5)

async def main_async():
    ui = StatusUI()
    
    def on_status_change(status: str):
        ui.set_status(status)

    audio_io = AudioIO()
    audio_io.start()

    client = GeminiLiveClient(audio_io, on_status_change=on_status_change)
    
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
