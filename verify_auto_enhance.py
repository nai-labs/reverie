import asyncio
import os
import sys
from unittest.mock import MagicMock

# Mock discord module before importing tts_manager
sys.modules["discord"] = MagicMock()

from unittest.mock import patch, AsyncMock
from tts_manager import TTSManager
from api_manager import APIManager
import logging

# Enable logging
logging.basicConfig(level=logging.DEBUG)

async def test_auto_enhancement():
    print("Testing Auto-Enhancement and v3 TTS...")
    
    # Mock Managers
    mock_conv_mgr = MagicMock()
    mock_conv_mgr.subfolder_path = "."
    
    # Mock APIManager
    mock_api_mgr = MagicMock(spec=APIManager)
    # Mock generate_voice_direction to return enhanced text
    mock_api_mgr.generate_voice_direction = AsyncMock(return_value="[laughter] Hello world!")
    
    # Initialize TTSManager with mocks
    with patch('tts_manager.characters', {"Gina": {"tts_url": "http://test/voice_id", "voice_settings": {}}}), \
         patch('tts_manager.ELEVENLABS_API_KEY', "fake_key"):
        
        tts_manager = TTSManager("Gina", mock_conv_mgr)
        
        # Mock aiohttp for TTS
        with patch('tts_manager.aiohttp.ClientSession') as MockSession:
            mock_session_instance = MagicMock()
            MockSession.return_value = mock_session_instance
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock()
            
            mock_post_ctx = MagicMock()
            mock_post_ctx.__aenter__ = AsyncMock()
            mock_post_ctx.__aexit__ = AsyncMock()
            
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=b"fake_audio_data")
            mock_post_ctx.__aenter__.return_value = mock_response
            
            mock_session_instance.post.return_value = mock_post_ctx
            
            # Simulate the flow in !say3
            original_text = "Hello world!"
            print(f"Original Text: {original_text}")
            
            # 1. Enhance
            enhanced_text = await mock_api_mgr.generate_voice_direction(original_text)
            print(f"Enhanced Text: {enhanced_text}")
            
            if enhanced_text == "[laughter] Hello world!":
                print("SUCCESS: Auto-enhancement mock called correctly.")
            else:
                print(f"FAILURE: Auto-enhancement returned {enhanced_text}")
            
            # 2. Generate TTS
            result = await tts_manager.generate_v3_tts(enhanced_text)
            
            if result and os.path.exists(result):
                print(f"SUCCESS: Generated file at {result}")
                
                # Verify request data used enhanced text
                call_args = mock_session_instance.post.call_args
                if call_args:
                    args, kwargs = call_args
                    data = kwargs.get('json', {})
                    if data.get('text') == enhanced_text:
                        print("SUCCESS: TTS called with enhanced text.")
                    else:
                        print(f"FAILURE: TTS called with '{data.get('text')}'")
                
                os.remove(result)
            else:
                print("FAILURE: No file generated")

if __name__ == "__main__":
    asyncio.run(test_auto_enhancement())
