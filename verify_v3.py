import asyncio
import os
import sys
from unittest.mock import MagicMock

# Mock discord module before importing tts_manager
sys.modules["discord"] = MagicMock()

from unittest.mock import patch, AsyncMock
from tts_manager import TTSManager
from conversation_manager import ConversationManager
import logging

# Enable logging
logging.basicConfig(level=logging.DEBUG)

async def test_v3_tts():
    print("Testing ElevenLabs v3 TTS...")
    
    # Mock ConversationManager
    mock_conv_mgr = MagicMock(spec=ConversationManager)
    mock_conv_mgr.subfolder_path = "."
    
    # Initialize TTSManager
    # We need to mock 'characters' import in tts_manager or just patch the dict lookup
    with patch('tts_manager.characters', {"Gina": {"tts_url": "http://test/voice_id", "voice_settings": {}}}), \
         patch('tts_manager.ELEVENLABS_API_KEY', "fake_key"):
        
        manager = TTSManager("Gina", mock_conv_mgr)
        
        # Mock aiohttp.ClientSession
        with patch('tts_manager.aiohttp.ClientSession') as MockSession:
            mock_session_instance = MagicMock()
            MockSession.return_value = mock_session_instance
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock()
            
            mock_post_ctx = MagicMock()
            mock_post_ctx.__aenter__ = AsyncMock()
            mock_post_ctx.__aexit__ = AsyncMock()
            
            # Configure success response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b"fake_audio_data")
            mock_post_ctx.__aenter__.return_value = mock_response
            
            mock_session_instance.post.return_value = mock_post_ctx
            
            # Run test
            text = "Hello [laughter]"
            result = await manager.generate_v3_tts(text)
            
            if result and os.path.exists(result):
                print(f"SUCCESS: Generated file at {result}")
                # Verify request data
                call_args = mock_session_instance.post.call_args
                if call_args:
                    args, kwargs = call_args
                    data = kwargs.get('json', {})
                    if data.get('model_id') == 'eleven_v3':
                        print("SUCCESS: Correct model ID used (eleven_v3)")
                    else:
                        print(f"FAILURE: Incorrect model ID: {data.get('model_id')}")
                
                # Clean up
                os.remove(result)
            else:
                print("FAILURE: No file generated")

if __name__ == "__main__":
    asyncio.run(test_v3_tts())
