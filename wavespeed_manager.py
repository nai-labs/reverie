import asyncio
import os
import logging
import aiohttp
import base64
from config import WAVESPEED_API_KEY, WAVESPEED_API_URL

logger = logging.getLogger(__name__)


class WavespeedManager:
    """Manager for Wavespeed AI API integration, specifically InfiniteTalk."""
    
    def __init__(self):
        self.api_key = WAVESPEED_API_KEY
        if not self.api_key:
            logger.warning("WAVESPEED_API_KEY is not set in environment variables")
        
        self.base_url = WAVESPEED_API_URL
        self.model_id = "wavespeed-ai/infinitetalk"
        self.poll_interval = 2  # seconds between status checks
        
        logger.info(f"Initialized WavespeedManager with model: {self.model_id}")
    
    def _get_headers(self):
        """Get authorization headers for API requests."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    async def _file_to_base64(self, file_path: str) -> str:
        """Convert a file to base64 data URI."""
        with open(file_path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        
        # Determine mime type
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4'
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')
        
        return f"data:{mime_type};base64,{data}"
    
    async def _poll_for_result(self, session: aiohttp.ClientSession, request_id: str) -> str | None:
        """Poll the API for task completion and return the result URL."""
        result_url = f"{self.base_url}/predictions/{request_id}/result"
        headers = self._get_headers()
        
        logger.info(f"Polling for result: {request_id}")
        
        while True:
            await asyncio.sleep(self.poll_interval)
            
            try:
                async with session.get(result_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Error polling result: {response.status} - {error_text}")
                        continue
                    
                    data = await response.json()
                    
                    # Wavespeed API returns response nested in 'data' object
                    response_data = data.get('data', data)
                    status = response_data.get('status')
                    
                    logger.debug(f"Poll status: {status}")
                    
                    if status == 'completed':
                        # Extract the video URL from the result
                        # Check multiple possible locations for the output
                        output = response_data.get('output') or response_data.get('outputs')
                        if output:
                            # Output could be a URL string or nested structure
                            if isinstance(output, str):
                                return output
                            elif isinstance(output, dict):
                                return output.get('video') or output.get('url')
                            elif isinstance(output, list) and len(output) > 0:
                                return output[0]
                        logger.error(f"Completed but no output found: {data}")
                        return None
                    
                    elif status == 'failed':
                        error = response_data.get('error', 'Unknown error')
                        logger.error(f"Task failed: {error}")
                        return None
                    
                    elif status in ['created', 'processing', 'pending', 'queued']:
                        # Still in progress, continue polling
                        progress = response_data.get('progress', '')
                        if progress:
                            print(f"Progress: {progress}")
                        continue
                    
                    else:
                        logger.warning(f"Unknown status: {status} - Full response: {data}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error during polling: {e}")
                await asyncio.sleep(self.poll_interval)
    
    # Supported Wavespeed models for video generation
    SUPPORTED_MODELS = {
        "infinitetalk": "wavespeed-ai/infinitetalk",
        "infinitetalk-fast": "wavespeed-ai/infinitetalk-fast",
        "hunyuan-avatar": "wavespeed-ai/hunyuan-avatar",
        "wan-s2v": "wavespeed-ai/wan-2.2/speech-to-video"
    }
    
    # Lipsync models
    LIPSYNC_MODELS = {
        "veed": "veed/lipsync"
    }
    
    async def generate_video(
        self,
        image_path: str,
        audio_path: str,
        model: str = "infinitetalk",
        prompt: str = None,
        resolution: str = "480p"
    ) -> str | None:
        """
        Generate a video using a Wavespeed model.
        
        Args:
            image_path: Path to the source image file
            audio_path: Path to the audio file
            model: Model to use ("infinitetalk", "infinitetalk-fast", "hunyuan-avatar")
            prompt: Optional text prompt for expression/pose guidance
            resolution: Video resolution ("480p" or "720p")
        
        Returns:
            URL to the generated video, or None if failed
        """
        if not self.api_key:
            logger.error("WAVESPEED_API_KEY is not configured")
            return None
        
        # Validate model
        model_id = self.SUPPORTED_MODELS.get(model)
        if not model_id:
            logger.error(f"Unsupported model: {model}. Supported: {list(self.SUPPORTED_MODELS.keys())}")
            return None
        
        logger.info(f"Generating video with {model} ({model_id}) - image: {image_path}")
        
        try:
            # Convert files to base64
            image_data = await self._file_to_base64(image_path)
            audio_data = await self._file_to_base64(audio_path)
            
            # Build request payload
            payload = {
                "image": image_data,
                "audio": audio_data,
                "resolution": resolution,
                "seed": -1  # Random seed
            }
            
            # Add optional prompt
            if prompt:
                payload["prompt"] = prompt
            
            async with aiohttp.ClientSession() as session:
                # Submit the task
                submit_url = f"{self.base_url}/{model_id}"
                headers = self._get_headers()
                
                logger.info(f"Submitting task to: {submit_url}")
                
                async with session.post(submit_url, json=payload, headers=headers) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        logger.error(f"Failed to submit task: {response.status} - {error_text}")
                        return None
                    
                    data = await response.json()
                    
                    # Wavespeed API returns response nested in 'data' object
                    response_data = data.get('data', data)
                    request_id = response_data.get('id') or response_data.get('requestId') or response_data.get('request_id')
                    
                    if not request_id:
                        logger.error(f"No request ID in response: {data}")
                        return None
                    
                    logger.info(f"Task submitted with ID: {request_id}")
                    
                    # Poll for result
                    video_url = await self._poll_for_result(session, request_id)
                    
                    if video_url:
                        logger.info(f"Video generated successfully: {video_url}")
                    
                    return video_url
                    
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating Wavespeed video: {e}", exc_info=True)
            return None
    
    # Backward compatibility wrapper
    async def generate_infinitetalk_video(self, image_path: str, audio_path: str, prompt: str = None, resolution: str = "480p") -> str | None:
        """Backward compatibility wrapper for generate_video with infinitetalk model."""
        return await self.generate_video(image_path, audio_path, model="infinitetalk", prompt=prompt, resolution=resolution)
    
    async def generate_lipsync(
        self,
        video_path: str,
        audio_path: str,
        model: str = "veed"
    ) -> str | None:
        """
        Generate a lipsynced video using Wavespeed lipsync models.
        
        Args:
            video_path: Path to the source video file
            audio_path: Path to the audio file to sync
            model: Lipsync model to use ("veed")
        
        Returns:
            URL to the lipsynced video, or None if failed
        """
        if not self.api_key:
            logger.error("WAVESPEED_API_KEY is not configured")
            return None
        
        # Validate model
        model_id = self.LIPSYNC_MODELS.get(model)
        if not model_id:
            logger.error(f"Unsupported lipsync model: {model}. Supported: {list(self.LIPSYNC_MODELS.keys())}")
            return None
        
        logger.info(f"Generating lipsync video with {model} ({model_id})")
        
        try:
            # Convert files to base64
            video_data = await self._file_to_base64(video_path)
            audio_data = await self._file_to_base64(audio_path)
            
            # Build request payload
            payload = {
                "video": video_data,
                "audio": audio_data
            }
            
            async with aiohttp.ClientSession() as session:
                # Submit the task
                submit_url = f"{self.base_url}/{model_id}"
                headers = self._get_headers()
                
                logger.info(f"Submitting lipsync task to: {submit_url}")
                
                async with session.post(submit_url, json=payload, headers=headers) as response:
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        logger.error(f"Failed to submit lipsync task: {response.status} - {error_text}")
                        return None
                    
                    data = await response.json()
                    
                    response_data = data.get('data', data)
                    request_id = response_data.get('id') or response_data.get('requestId') or response_data.get('request_id')
                    
                    if not request_id:
                        logger.error(f"No request ID in response: {data}")
                        return None
                    
                    logger.info(f"Lipsync task submitted with ID: {request_id}")
                    
                    # Poll for result
                    video_url = await self._poll_for_result(session, request_id)
                    
                    if video_url:
                        logger.info(f"Lipsync video generated successfully: {video_url}")
                    
                    return video_url
                    
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating lipsync video: {e}", exc_info=True)
            return None
    
    async def test_auth(self) -> bool:
        """Test authentication with Wavespeed API."""
        if not self.api_key:
            logger.error("WAVESPEED_API_KEY is not configured")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                # Try to access a simple endpoint to verify auth
                # Using models list or account endpoint if available
                test_url = f"{self.base_url.replace('/api/v3', '')}/api/v1/user"
                headers = self._get_headers()
                
                async with session.get(test_url, headers=headers) as response:
                    if response.status == 200:
                        logger.info("Wavespeed authentication successful")
                        return True
                    else:
                        logger.error(f"Wavespeed auth failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error testing Wavespeed auth: {e}")
            return False
