import asyncio
import json
import base64
import os
import websockets
from typing import Optional, Callable
from .tools import TOOLS_SCHEMA, dispatch_tool
from .audio import AudioIO

class GeminiLiveClient:
    def __init__(self, audio_io: AudioIO, on_status_change: Optional[Callable[[str], None]] = None):
        self.audio = audio_io
        self.ws = None
        self._receive_task = None
        self._send_task = None
        self.running = False
        self.on_status_change = on_status_change or (lambda s: None)

    def _get_api_key(self) -> str:
        key = os.environ.get("GEMINI_PRIMARY_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise ValueError("API Key missing: Please set GEMINI_PRIMARY_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY.")
        return key

    async def connect(self):
        api_key = self._get_api_key()
        # Using the standard gemini bidi endpoint
        uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={api_key}"
        
        self.ws = await websockets.connect(uri)
        
        # Send setup message
        setup_msg = {
            "setup": {
                "model": "models/gemini-2.0-flash-exp",
                "systemInstruction": {
                    "parts": [{"text": "You are VoicePilot, a native macOS real-time voice pair-programming assistant. Keep responses brief."}]
                },
                "tools": [{"functionDeclarations": TOOLS_SCHEMA}],
            }
        }
        await self.ws.send(json.dumps(setup_msg))
        
        # Wait for setup complete
        raw_response = await self.ws.recv()
        setup_response = json.loads(raw_response)
        if "setupComplete" not in setup_response:
            print("Warning: Expected setupComplete, got:", setup_response)
            
        self.running = True
        self.on_status_change("LIVE")
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._send_task = asyncio.create_task(self._send_loop())

    async def _send_loop(self):
        try:
            while self.running:
                # Read from audio queue
                chunk = await self.audio.input_queue.get()
                b64_data = base64.b64encode(chunk).decode("utf-8")
                msg = {
                    "realtimeInput": {
                        "mediaChunks": [
                            {
                                "mimeType": "audio/pcm;rate=16000",
                                "data": b64_data
                            }
                        ]
                    }
                }
                await self.ws.send(json.dumps(msg))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in send loop: {e}")

    async def _receive_loop(self):
        try:
            while self.running:
                raw_msg = await self.ws.recv()
                msg = json.loads(raw_msg)
                
                if "serverContent" in msg:
                    server_content = msg["serverContent"]
                    
                    if "interrupted" in server_content and server_content["interrupted"]:
                        self.audio.clear_output_buffer()
                    
                    model_turn = server_content.get("modelTurn", {})
                    parts = model_turn.get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            # It's audio
                            self.on_status_change("SPEAKING")
                            b64_data = part["inlineData"]["data"]
                            audio_bytes = base64.b64decode(b64_data)
                            self.audio.play_audio(audio_bytes)
                        elif "executableCode" in part:
                            pass # We can handle or log executable code
                        elif "codeExecutionResult" in part:
                            pass
                            
                    if server_content.get("turnComplete"):
                        self.on_status_change("LISTENING")
                
                elif "toolCall" in msg:
                    self.on_status_change("RUNNING_TOOL")
                    tool_call = msg["toolCall"]
                    function_calls = tool_call.get("functionCalls", [])
                    
                    responses = []
                    for fc in function_calls:
                        name = fc["name"]
                        args = fc.get("args", {})
                        id_ = fc["id"]
                        
                        result_str = await dispatch_tool(name, args)
                        
                        responses.append({
                            "id": id_,
                            "name": name,
                            "response": {"result": result_str}
                        })
                        
                    tool_resp = {
                        "toolResponse": {
                            "functionResponses": responses
                        }
                    }
                    await self.ws.send(json.dumps(tool_resp))
                    self.on_status_change("LIVE")
                    
        except asyncio.CancelledError:
            pass
        except websockets.ConnectionClosed:
            self.running = False
            self.on_status_change("DISCONNECTED")
        except Exception as e:
            print(f"Error in receive loop: {e}")
            self.on_status_change("ERROR")

    async def disconnect(self):
        self.running = False
        if self._send_task:
            self._send_task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
        if self.ws:
            await self.ws.close()
