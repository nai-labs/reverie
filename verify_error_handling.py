import asyncio
import aiohttp
from unittest.mock import MagicMock, patch, AsyncMock
from api_manager import APIManager
import logging

# Enable logging
logging.basicConfig(level=logging.DEBUG)

async def test_network_error():
    print("Testing Network Error Handling...")
    manager = APIManager()
    
    # Mock the session context manager
    # Patch aiohttp.ClientSession where it is used in api_manager
    with patch('api_manager.aiohttp.ClientSession') as MockSession:
        # The instance returned by ClientSession()
        mock_session_instance = MagicMock()
        MockSession.return_value = mock_session_instance
        
        # async with ClientSession() as session:
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock()
        
        # session.post(...) returns a context manager
        mock_post_ctx = MagicMock()
        # async with session.post(...) as response:
        mock_post_ctx.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Simulated Network Error"))
        mock_post_ctx.__aexit__ = AsyncMock()
        
        mock_session_instance.post.return_value = mock_post_ctx
        
        # Test Anthropic
        print("\n--- Anthropic ---")
        manager.current_llm = "anthropic"
        response = await manager.generate_response("hi", [], "system")
        print(f"Response: {response}")
        if "trouble connecting" in response:
            print("SUCCESS: Anthropic network error handled.")
        else:
            print("FAILURE: Anthropic network error NOT handled.")

        # Test OpenRouter
        print("\n--- OpenRouter ---")
        manager.current_llm = "openrouter"
        # We need to reset the side effect if we wanted different behavior, but here same error is fine
        response = await manager.generate_response("hi", [], "system")
        print(f"Response: {response}")
        if "trouble connecting" in response:
            print("SUCCESS: OpenRouter network error handled.")
        else:
            print("FAILURE: OpenRouter network error NOT handled.")

        # Test LMStudio
        print("\n--- LMStudio ---")
        manager.current_llm = "lmstudio"
        response = await manager.generate_response("hi", [], "system")
        print(f"Response: {response}")
        if "cannot connect" in response:
            print("SUCCESS: LMStudio network error handled.")
        else:
            print("FAILURE: LMStudio network error NOT handled.")

if __name__ == "__main__":
    asyncio.run(test_network_error())
