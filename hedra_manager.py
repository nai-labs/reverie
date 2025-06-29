# hedra_manager.py
import aiohttp
import logging
import os
import asyncio
from config import HEDRA_BASE_URL, HEDRA_API_KEY

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HedraManager:
    def __init__(self):
        self.base_url = HEDRA_BASE_URL
        self.api_key = HEDRA_API_KEY

        if not self.api_key:
            logger.error("Hedra API key is not set. Please set HEDRA_API_KEY in your .env file.")
            raise ValueError("Hedra API key is required but not set.")

    async def upload_audio(self, audio_path):
        """Upload audio file to Hedra."""
        try:
            url = f"{self.base_url}/v1/audio"
            headers = {'X-API-KEY': self.api_key}

            logger.info("Uploading audio file...")

            async with aiohttp.ClientSession() as session:
                if not os.path.exists(audio_path):
                    logger.error("Audio file not found")
                    return None

                with open(audio_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=os.path.basename(audio_path), content_type='audio/mpeg')
                    async with session.post(url, headers=headers, data=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info("Audio upload completed")
                            return result.get('url')
                        else:
                            error_text = await response.text()
                            logger.error(f"Audio upload failed: {error_text}")
                            return None
        except Exception as e:
            logger.error(f"Error uploading audio: {str(e)}")
            return None

    async def upload_portrait(self, image_path, aspect_ratio="1:1"):
        """Upload portrait image to Hedra."""
        try:
            url = f"{self.base_url}/v1/portrait"
            headers = {'X-API-KEY': self.api_key}
            params = {'aspect_ratio': aspect_ratio}

            logger.info("Uploading portrait image...")

            async with aiohttp.ClientSession() as session:
                if not os.path.exists(image_path):
                    logger.error("Image file not found")
                    return None

                with open(image_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=os.path.basename(image_path), content_type='image/png')
                    async with session.post(url, headers=headers, params=params, data=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info("Portrait upload completed")
                            return result.get('url')
                        else:
                            error_text = await response.text()
                            logger.error(f"Portrait upload failed: {error_text}")
                            return None
        except Exception as e:
            logger.error(f"Error uploading portrait: {str(e)}")
            return None

    async def generate_character(self, avatar_image_url, audio_url, aspect_ratio="1:1"):
        """Initialize character generation with Hedra."""
        try:
            url = f"{self.base_url}/v1/characters"
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            data = {
                "avatarImage": avatar_image_url,
                "audioSource": "audio",
                "voiceUrl": audio_url,
                "aspectRatio": aspect_ratio,
                "text": ""
            }

            logger.info("Initializing character generation...")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("Character generation initialized")
                        return result.get('jobId')
                    else:
                        error_text = await response.text()
                        logger.error(f"Character generation failed: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error in character generation: {str(e)}")
            return None

    async def get_project_status(self, job_id):
        """Get the status of a project/job."""
        try:
            url = f"{self.base_url}/v1/projects/{job_id}"
            headers = {'X-API-KEY': self.api_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Error getting project status: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error checking project status: {str(e)}")
            return None

    async def wait_for_completion(self, job_id, timeout=300, check_interval=5):
        """Wait for the video generation to complete."""
        start_time = asyncio.get_event_loop().time()
        last_progress = None
        last_stage = None
        
        logger.info("Starting video generation...")
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            project_status = await self.get_project_status(job_id)
            if not project_status:
                return None

            status = project_status.get('status', '').lower()
            progress = project_status.get('progress')
            stage = project_status.get('stage')
            
            # Log progress updates only when they change
            if progress is not None and progress != last_progress:
                progress_percent = int(progress * 100)
                logger.info(f"Progress: {progress_percent}%")
                last_progress = progress

            # Log stage updates only when they change
            if stage and stage != last_stage:
                logger.info(f"Current stage: {stage}")
                last_stage = stage

            if status == 'completed':
                logger.info("Video generation completed successfully")
                video_url = project_status.get('videoUrl')
                if video_url:
                    return video_url
                else:
                    logger.error("No video URL found in completed project")
                    return None
            elif status == 'failed':
                error_msg = project_status.get('errorMessage', 'Unknown error')
                logger.error(f"Video generation failed: {error_msg}")
                return None

            # Only continue waiting if status is not completed and not failed
            if status not in ['completed', 'failed']:
                await asyncio.sleep(check_interval)
            else:
                break

        logger.error("Video generation timed out")
        return None

    async def generate_video(self, audio_path, image_path, aspect_ratio="1:1"):
        """Complete flow to generate a video from audio and image files."""
        logger.info("Starting Hedra video generation process...")

        # Upload audio
        audio_url = await self.upload_audio(audio_path)
        if not audio_url:
            return None, "Failed to upload audio"

        # Upload image
        image_url = await self.upload_portrait(image_path, aspect_ratio)
        if not image_url:
            return None, "Failed to upload image"

        # Generate character
        job_id = await self.generate_character(image_url, audio_url, aspect_ratio)
        if not job_id:
            return None, "Failed to initialize character generation"

        # Wait for completion
        video_url = await self.wait_for_completion(job_id)
        if not video_url:
            return None, "Failed to generate video or timeout"

        logger.info("Video generation process completed")
        return video_url, None
