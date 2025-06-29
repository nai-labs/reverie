import asyncio
import websockets
import json
import logging
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

class RealtimeManager:
    def __init__(self, character_name, voice_settings=None):
        self.character_name = character_name
        self.voice_settings = voice_settings or {}
        self.ws = None
        self.session_config = None
        
    async def connect(self):
        """Establish WebSocket connection with OpenAI's realtime API."""
        try:
            self.ws = await websockets.connect(
                'wss://api.openai.com/v1/audio/realtime',
                extra_headers={
                    'Authorization': f'Bearer {OPENAI_API_KEY}',
                    'Content-Type': 'application/json'
                }
            )
            logger.info("Connected to OpenAI realtime API")
            
            # Initialize session with character-specific settings
            await self.initialize_session()
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI realtime API: {e}")
            raise

    async def initialize_session(self):
        """Initialize the realtime session with character-specific configuration."""
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": f"You are {self.character_name}. {self.voice_settings.get('instructions', '')}",
                "voice": self.voice_settings.get('voice', 'alloy'),
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            }
        }
        
        try:
            await self.ws.send(json.dumps(session_config))
            response = await self.ws.recv()
            logger.info(f"Session initialized: {response}")
            self.session_config = session_config
            
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            raise

    async def send_audio(self, audio_data):
        """Send audio data to the realtime API."""
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")
            
        try:
            message = {
                "type": "input_audio_buffer.append",
                "audio": audio_data  # Base64 encoded audio data
            }
            await self.ws.send(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Failed to send audio data: {e}")
            raise

    async def receive_audio(self):
        """Receive audio data from the realtime API."""
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")
            
        try:
            while True:
                response = await self.ws.recv()
                event = json.loads(response)
                
                if event.get("type") == "response.audio.delta":
                    yield event.get("delta")  # Base64 encoded audio data
                elif event.get("type") == "response.audio.done":
                    break
                    
        except Exception as e:
            logger.error(f"Failed to receive audio data: {e}")
            raise

    async def close(self):
        """Close the WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.ws = None
            logger.info("WebSocket connection closed")
