import asyncio
import os
import logging
from dotenv import load_dotenv
import aiohttp
import base64
import replicate
from config import API_POLL_INTERVAL, DEFAULT_VIDEO_DURATION, CIVITAI_API_TOKEN

load_dotenv()

logger = logging.getLogger(__name__)

class ReplicateManager:
    def __init__(self):
        # Get token from .env file
        from dotenv import dotenv_values
        self.config = dotenv_values('.env')
        self.token = self.config.get('REPLICATE_API_TOKEN')
        if not self.token:
            raise ValueError("REPLICATE_API_TOKEN is not set in environment variables")
        if not self.token.startswith('r8_'):
            raise ValueError("REPLICATE_API_TOKEN must start with 'r8_'")
            
        logger.info(f"Initializing Replicate manager with token starting with: {self.token[:10]}...")
        logger.debug(f"Full token length: {len(self.token)} characters")
        # SadTalker model
        self.model = "cjwbw/sadtalker"
        self.version = "a519cc0cfebaaeade068b23899165a11ec76aaa1d2b313d40d214f204ec957a3"
        # Recraft model for image generation
        self.recraft_model = "recraft-ai/recraft-v3"
        self.recraft_version = "dd1d9248c3b1c6c7ff7c48e5d35d7722a62c6dfa8d3b5c04c2cd57111f95f6da"
        
        
        # Default values for sadtalker adjustable parameters
        self.expression_scale = 1.0
        self.pose_style = 0
        
        # Default values for sadtalker other parameters
        self.facerender = "facevid2vid"
        self.preprocess = "crop"
        self.still_mode = False
        self.use_enhancer = False
        self.use_eyeblink = True
        self.size_of_image = 256
        self.pose_style = 38
        self.expression_scale = 1.2
        
        # video-retalker init
        self.video_retalking_model = "chenxwh/video-retalking"
        self.video_retalking_version = "db5a650c807b007dc5f9e5abe27c53e1b62880d1f94d218d27ce7fa802711d67"

        # Kling model for image-to-video
        self.kling_model = "kwaivgi/kling-v2.1"
        
        # LatentSync model for lip sync
        self.latentsync_model = "bytedance/latentsync"
        self.latentsync_version = "839aba2e94ed8b18657a685c07f532946337e93c216e152c0bdf7b66cb54877d"

        # WAN model identifier
        self.wan_model_identifier = "wavespeedai/wan-2.1-i2v-480p" # No version hash needed for library

        # Omni-Human model
        self.omni_human_model = "bytedance/omni-human"

        # Wan S2V model
        self.wan_s2v_model = "wan-video/wan-2.2-s2v"

        # WAN LoRA models
        self.wan_lora_models = {
            "wan-2.2-fast": "wan-video/wan-2.2-i2v-fast",      # HuggingFace LoRAs
            "wan-2.1-lora": "wan-video/wan2.1-with-lora"       # CivitAI LoRAs
        }

        # Instantiate the replicate client
        # The client automatically uses the REPLICATE_API_TOKEN environment variable
        self.replicate_client = replicate.Client(api_token=self.token)

    async def _poll_prediction(self, session, prediction_id, headers):
        """Helper method to poll a Replicate prediction until completion."""
        last_log_line = ""
        while True:
            await asyncio.sleep(API_POLL_INTERVAL)
            async with session.get(f"https://api.replicate.com/v1/predictions/{prediction_id}", 
                                 headers=headers) as status_response:
                if status_response.status != 200:
                    logger.error(f"Error checking status: {await status_response.text()}")
                    return None
                
                status_data = await status_response.json()
                status = status_data.get('status')
                
                # Check for logs to print progress
                logs = status_data.get('logs', '')
                if logs:
                    current_log_lines = logs.strip().split('\n')
                    if current_log_lines:
                        new_last_line = current_log_lines[-1]
                        if new_last_line != last_log_line:
                            # Print progress if it looks like a progress bar or percentage
                            if '%' in new_last_line or 'it/s' in new_last_line or 'steps' in new_last_line.lower():
                                print(f"Progress: {new_last_line.strip()}")
                            last_log_line = new_last_line

                logger.debug(f"Prediction status: {status}")
                
                if status == 'succeeded':
                    return status_data.get('output')
                elif status == 'failed':
                    logger.error(f"Prediction failed: {status_data.get('error')}")
                    return None
                elif status not in ['starting', 'processing']:
                    logger.warning(f"Unexpected status: {status}")
                    return None

    async def generate_image(self, prompt, size="1024x1536"):
        try:
            logger.info(f"Creating image prediction with Replicate...")
            # Use aiohttp for direct API access
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }
                data = {
                    'version': self.recraft_version,
                    'input': {
                        'prompt': prompt,
                        'size': size
                    }
                }
                async with session.post('https://api.replicate.com/v1/predictions', 
                                     headers=headers, 
                                     json=data) as response:
                    if response.status != 201:
                        error_text = await response.text()
                        logger.error(f"Error response: {error_text}")
                        return None
                    
                    prediction = await response.json()
                    prediction_id = prediction.get('id')
                    logger.debug(f"Prediction created with ID: {prediction_id}")

                    # Poll for completion
                    output = await self._poll_prediction(session, prediction_id, headers)
                    if output:
                        return output[0] if isinstance(output, list) else output
                    return None

        except Exception as e:
            logger.error(f"Error in generate_image: {str(e)}", exc_info=True)
            return None

    async def generate_video_retalking(self, face_path, audio_path):
        try:
            logger.info(f"Creating video retalking prediction...")
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }
                # Convert files to base64
                with open(face_path, "rb") as f:
                    face_data = base64.b64encode(f.read()).decode('utf-8')
                with open(audio_path, "rb") as f:
                    audio_data = base64.b64encode(f.read()).decode('utf-8')

                data = {
                    'version': self.video_retalking_version,
                    'input': {
                        'face': f"data:image/jpeg;base64,{face_data}",
                        'input_audio': f"data:audio/wav;base64,{audio_data}"
                    }
                }
                async with session.post('https://api.replicate.com/v1/predictions', 
                                     headers=headers, 
                                     json=data) as response:
                    if response.status != 201:
                        error_text = await response.text()
                        logger.error(f"Error response: {error_text}")
                        return None
                    
                    prediction = await response.json()
                    prediction_id = prediction.get('id')
                    logger.debug(f"Prediction created with ID: {prediction_id}")

                    # Poll for completion
                    return await self._poll_prediction(session, prediction_id, headers)

        except Exception as e:
            logger.error(f"Error in generate_video_retalking: {str(e)}", exc_info=True)
            return None
    
        

    async def generate_talking_face(
        self,
        driven_audio,
        source_image,
        facerender=None,
        pose_style=None,
        preprocess=None,
        still_mode=None,
        use_enhancer=None,
        use_eyeblink=None,
        size_of_image=None,
        expression_scale=None
    ):
        try:
            # Use instance variables if no value is provided
            facerender = facerender if facerender is not None else self.facerender
            pose_style = pose_style if pose_style is not None else self.pose_style
            preprocess = preprocess if preprocess is not None else self.preprocess
            still_mode = still_mode if still_mode is not None else self.still_mode
            use_enhancer = use_enhancer if use_enhancer is not None else self.use_enhancer
            use_eyeblink = use_eyeblink if use_eyeblink is not None else self.use_eyeblink
            size_of_image = size_of_image if size_of_image is not None else self.size_of_image
            expression_scale = expression_scale if expression_scale is not None else self.expression_scale

            logger.debug(f"Initiating API call with parameters: "
                        f"driven_audio={driven_audio}, source_image={source_image}, "
                        f"facerender={facerender}, pose_style={pose_style}, "
                        f"preprocess={preprocess}, still_mode={still_mode}, "
                        f"use_enhancer={use_enhancer}, use_eyeblink={use_eyeblink}, "
                        f"size_of_image={size_of_image}, expression_scale={expression_scale}")

            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }
                data = {
                    'version': self.version,
                    'input': {
                        "driven_audio": driven_audio,
                        "source_image": source_image,
                        "facerender": facerender,
                        "pose_style": pose_style,
                        "preprocess": preprocess,
                        "still_mode": still_mode,
                        "use_enhancer": use_enhancer,
                        "use_eyeblink": use_eyeblink,
                        "size_of_image": size_of_image,
                        "expression_scale": expression_scale
                    }
                }
                async with session.post('https://api.replicate.com/v1/predictions', 
                                     headers=headers, 
                                     json=data) as response:
                    if response.status != 201:
                        error_text = await response.text()
                        logger.error(f"Error response: {error_text}")
                        return None
                    
                    prediction = await response.json()
                    prediction_id = prediction.get('id')
                    logger.debug(f"Prediction created with ID: {prediction_id}")

                    # Poll for completion
                    return await self._poll_prediction(session, prediction_id, headers)

        except Exception as e:
            logger.error(f"Error in generate_talking_face: {str(e)}", exc_info=True)
        
        return None

    def set_expression_scale(self, value):
        try:
            self.expression_scale = float(value)
            return f"Expression scale set to {self.expression_scale}"
        except ValueError:
            return "Invalid value. Please provide a number for expression scale."

    def set_pose_style(self, value):
        try:
            self.pose_style = int(value)
            return f"Pose style set to {self.pose_style}"
        except ValueError:
            return "Invalid value. Please provide an integer for pose style."

    def set_facerender(self, value):
        if value in ["facevid2vid", "pirender"]:
            self.facerender = value
            return f"Facerender set to {self.facerender}"
        else:
            return "Invalid value. Facerender must be 'facevid2vid' or 'pirender'."

    def set_preprocess(self, value):
        if value in ["full", "crop"]:
            self.preprocess = value
            return f"Preprocess set to {self.preprocess}"
        else:
            return "Invalid value. Preprocess must be 'full' or 'crop'."

    def set_still_mode(self, value):
        if value.lower() in ['true', 'false']:
            self.still_mode = value.lower() == 'true'
            return f"Still mode set to {self.still_mode}"
        else:
            return "Invalid value. Still mode must be 'true' or 'false'."

    def set_use_enhancer(self, value):
        if value.lower() in ['true', 'false']:
            self.use_enhancer = value.lower() == 'true'
            return f"Use enhancer set to {self.use_enhancer}"
        else:
            return "Invalid value. Use enhancer must be 'true' or 'false'."

    def set_use_eyeblink(self, value):
        if value.lower() in ['true', 'false']:
            self.use_eyeblink = value.lower() == 'true'
            return f"Use eyeblink set to {self.use_eyeblink}"
        else:
            return "Invalid value. Use eyeblink must be 'true' or 'false'."

    def set_size_of_image(self, value):
        try:
            self.size_of_image = int(value)
            return f"Size of image set to {self.size_of_image}"
        except ValueError:
            return "Invalid value. Please provide an integer for size of image."

    async def test_auth(self):
        """Test the authentication with Replicate API"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }
                async with session.get('https://api.replicate.com/v1/account', headers=headers) as response:
                    if response.status == 200:
                        account_data = await response.json()
                        logger.info(f"Authentication successful. Account: {account_data.get('username')}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Authentication failed with status {response.status}: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Authentication test failed: {str(e)}", exc_info=True)
            return False

    async def generate_kling_video(self, image_path, prompt, duration=DEFAULT_VIDEO_DURATION):
        """Generate a video from an image using the Kling model."""
        logger.info(f"Generating Kling video with image: {image_path} and prompt: '{prompt}'")
        try:
            with open(image_path, "rb") as image_file:
                input_data = {
                    "start_image": image_file,
                    "prompt": prompt,
                    "duration": duration
                }
                output_url = await asyncio.to_thread(
                    self.replicate_client.run,
                    self.kling_model,
                    input=input_data
                )
                logger.info(f"Kling video generation successful. Output URL: {output_url}")
                return output_url
        except replicate.exceptions.ReplicateError as e:
            logger.error(f"Replicate API error during Kling video generation: {e}")
            return None
        except FileNotFoundError:
            logger.error(f"Image file not found for Kling video generation: {image_path}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Kling video generation: {e}", exc_info=True)
            return None

    async def apply_latentsync(self, video_url, audio_path):
        """Apply lip sync to a video using the LatentSync model."""
        try:
            logger.info(f"Creating LatentSync prediction...")
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }

                # Convert audio to base64
                with open(audio_path, "rb") as f:
                    audio_data = base64.b64encode(f.read()).decode('utf-8')

                data = {
                    'version': self.latentsync_version,
                    'input': {
                        'audio': f"data:audio/wav;base64,{audio_data}",
                        'video': video_url
                    }
                }

                async with session.post('https://api.replicate.com/v1/predictions', 
                                     headers=headers, 
                                     json=data) as response:
                    if response.status != 201:
                        error_text = await response.text()
                        logger.error(f"Error response: {error_text}")
                        return None
                    
                    prediction = await response.json()
                    prediction_id = prediction.get('id')
                    logger.debug(f"Prediction created with ID: {prediction_id}")

                    # Poll for completion
                    return await self._poll_prediction(session, prediction_id, headers)

        except Exception as e:
            logger.error(f"Error in apply_latentsync: {str(e)}", exc_info=True)
            return None

    async def generate_wan_video(self, image_path, prompt):
        """Generates a video using the WAN I2V model via the replicate library."""
        logger.info(f"Generating WAN video with image: {image_path} and prompt: '{prompt}'")
        try:
            # The replicate library handles opening the file
            with open(image_path, "rb") as image_file:
                input_data = {
                    "image": image_file,
                    "prompt": prompt
                }
                # Use replicate.run which handles waiting for the result
                output_url = await asyncio.to_thread(
                    self.replicate_client.run,
                    self.wan_model_identifier,
                    input=input_data
                )
                # replicate.run returns the output directly when completed
                logger.info(f"WAN video generation successful. Output URL: {output_url}")
                return output_url
        except replicate.exceptions.ReplicateError as e:
            logger.error(f"Replicate API error during WAN video generation: {e}")
            return None
        except FileNotFoundError:
            logger.error(f"Image file not found for WAN video generation: {image_path}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during WAN video generation: {e}", exc_info=True)
            return None

    async def generate_omni_human_video(self, image_path, audio_path):
        """Generates a video using the Omni-Human model via the replicate library."""
        logger.info(f"Generating Omni-Human video with image: {image_path} and audio: {audio_path}")
        try:
            with open(image_path, "rb") as image_file, open(audio_path, "rb") as audio_file:
                input_data = {
                    "image": image_file,
                    "audio": audio_file
                }
                output_url = await asyncio.to_thread(
                    self.replicate_client.run,
                    self.omni_human_model,
                    input=input_data
                )
                logger.info(f"Omni-Human video generation successful. Output URL: {output_url}")
                return output_url
        except replicate.exceptions.ReplicateError as e:
            logger.error(f"Replicate API error during Omni-Human video generation: {e}")
            return None
        except FileNotFoundError as e:
            logger.error(f"File not found for Omni-Human video generation: {e}")
            return None
            logger.error(f"Unexpected error during Omni-Human video generation: {e}", exc_info=True)
            return None

    async def generate_wan_s2v_video(self, image_path, audio_path, prompt):
        """Generates a video using the WAN S2V model via the Replicate API with progress updates."""
        logger.info(f"Generating WAN S2V video with image: {image_path}, audio: {audio_path}, and prompt: '{prompt}'")
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }
                
                # Convert files to base64
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                with open(audio_path, "rb") as f:
                    audio_data = base64.b64encode(f.read()).decode('utf-8')

                data = {
                    'version': self.wan_s2v_model.split(':')[1] if ':' in self.wan_s2v_model else None, # Handle if version is in string
                    # For models without explicit version in string, we might need to fetch it or use the owner/name format
                    # Replicate API usually prefers version hash for predictions, but some endpoints accept model name
                    # Let's try using the model name in the URL for creating prediction if version is missing
                }
                
                # Construct payload
                payload = {
                    "input": {
                        "image": f"data:image/jpeg;base64,{image_data}", # Assuming JPEG/PNG
                        "audio": f"data:audio/wav;base64,{audio_data}",   # Assuming WAV
                        "prompt": prompt
                    }
                }

                # If we don't have a version hash, we should probably fetch it or use the deployments endpoint
                # But wait, self.wan_s2v_model is "wan-video/wan-2.2-s2v"
                # We can use the replicate client to get the version, or just use the replicate client's create method which handles this?
                # Actually, replicate client's predictions.create is easier but it's synchronous? No, we can use asyncio.to_thread
                # But we want to poll manually.
                
                # Let's get the latest version first using our existing get_model_info or just hardcode if we knew it.
                # Better: Use the replicate client to create the prediction, then poll manually using the ID.
                
                prediction = await asyncio.to_thread(
                    self.replicate_client.predictions.create,
                    version=self.replicate_client.models.get("wan-video/wan-2.2-s2v").latest_version,
                    input={
                        "image": open(image_path, "rb"),
                        "audio": open(audio_path, "rb"),
                        "prompt": prompt
                    }
                )
                
                logger.info(f"WAN S2V prediction created with ID: {prediction.id}")
                
                # Poll for completion using our helper
                return await self._poll_prediction(session, prediction.id, headers)

        except Exception as e:
            logger.error(f"Error in generate_wan_s2v_video: {str(e)}", exc_info=True)
            return None

    async def get_model_info(self, model_name=None):
        """Get information about a model from Replicate API.
        Args:
            model_name: Optional model name (e.g., "kwaivgi/kling-v1.6-standard"). If not provided, uses self.model.
        """
        try:
            model_to_query = model_name if model_name else self.model
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }
                async with session.get(f'https://api.replicate.com/v1/models/{model_to_query}', 
                                     headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error getting model info: {await response.text()}")
                        return None
                    
                    model_data = await response.json()
                    versions = []
                    if 'latest_version' in model_data:
                        versions.append({
                            'id': model_data['latest_version']['id'],
                            'created_at': model_data['latest_version']['created_at']
                        })
                    return {
                        "name": model_data.get('name'),
                        "description": model_data.get('description'),
                        "versions": versions
                    }
        except Exception as e:
            logger.error(f"Error in get_model_info: {str(e)}", exc_info=True)
            return None

    def format_civitai_url(self, raw_url: str) -> str:
        """Format a CivitAI download URL by appending the API token.
        
        Input: https://civitai.com/api/download/models/2494041?type=Model&format=SafeTensor
        Output: https://civitai.com/api/download/models/2494041?type=Model&format=SafeTensor&token=XXX
        """
        if not CIVITAI_API_TOKEN:
            logger.error("CIVITAI_API_TOKEN is not set in environment variables")
            return raw_url
        
        # Check if token is already in URL
        if "token=" in raw_url:
            return raw_url
        
        # Append token
        separator = "&" if "?" in raw_url else "?"
        formatted_url = f"{raw_url}{separator}token={CIVITAI_API_TOKEN}"
        logger.info(f"Formatted CivitAI URL: {formatted_url[:80]}...")
        return formatted_url

    async def generate_wan_lora_video(self, image_path: str, prompt: str, lora_url: str = None, lora_scale: float = 1.0, lora_url_2: str = None, lora_scale_2: float = None, model: str = "wan-2.2-fast", num_frames: int = 81, fps: int = 16):
        """Generate a video using WAN with an optional LoRA.
        
        model options:
        - 'wan-2.2-fast': Uses lora_weights_transformer (HuggingFace URLs)
        - 'wan-2.1-lora': Uses hf_lora (CivitAI URLs)
        
        If lora_url is None, generates a plain image-to-video without LoRA.
        """
        if lora_url:
            logger.info(f"Generating WAN video with LoRA, model: {model}, lora_scale: {lora_scale}, frames: {num_frames}, fps: {fps}")
            if lora_url_2:
                logger.info(f"Using second LoRA with scale: {lora_scale_2}")
        else:
            logger.info(f"Generating WAN video (no LoRA), model: {model}, frames: {num_frames}, fps: {fps}")
        logger.info(f"Prompt: {prompt[:100]}...")
        
        # Get model identifier
        model_id = self.wan_lora_models.get(model)
        if not model_id:
            logger.error(f"Unknown WAN model: {model}")
            return None
        
        # Format CivitAI URL with token (only needed for wan-2.1-lora with a LoRA)
        formatted_lora_url = None
        if lora_url:
            if model == "wan-2.1-lora":
                formatted_lora_url = self.format_civitai_url(lora_url)
            else:
                # WAN 2.2 Fast uses HuggingFace URLs directly, no formatting needed
                formatted_lora_url = lora_url
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Token {self.token}',
                    'Content-Type': 'application/json'
                }
                
                # Convert image to base64
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                # Get the latest version of the model
                model_info = await self.get_model_info(model_id)
                if not model_info or not model_info.get('versions'):
                    logger.error(f"Could not get model version for {model_id}")
                    return None
                
                version_id = model_info['versions'][0]['id']
                
                # Build payload based on model
                if model == "wan-2.2-fast":
                    # WAN 2.2 Fast - base payload
                    payload = {
                        'version': version_id,
                        'input': {
                            'image': f"data:image/jpeg;base64,{image_data}",
                            'prompt': prompt,
                            'go_fast': True,
                            'num_frames': num_frames,
                            'frames_per_second': fps,
                            'resolution': '480p',
                            'disable_safety_checker': True
                        }
                    }
                    # Add LoRA if provided
                    if formatted_lora_url:
                        payload['input']['lora_weights_transformer'] = formatted_lora_url
                        payload['input']['lora_scale_transformer'] = lora_scale
                    # Add second LoRA if provided
                    if lora_url_2:
                        payload['input']['lora_weights_transformer_2'] = lora_url_2
                        payload['input']['lora_scale_transformer_2'] = lora_scale_2 or 1.0
                else:  # wan-2.1-lora
                    # WAN 2.1 - base payload
                    payload = {
                        'version': version_id,
                        'input': {
                            'image': f"data:image/jpeg;base64,{image_data}",
                            'prompt': prompt
                        }
                    }
                    # Add LoRA if provided
                    if formatted_lora_url:
                        payload['input']['hf_lora'] = formatted_lora_url
                        payload['input']['lora_scale'] = lora_scale
                
                lora_info = " with LoRA" if formatted_lora_url else " (no LoRA)"
                logger.info(f"Creating WAN prediction{lora_info} with model: {model_id}, version: {version_id}")
                
                async with session.post('https://api.replicate.com/v1/predictions', 
                                       headers=headers, 
                                       json=payload) as response:
                    if response.status != 201:
                        error_text = await response.text()
                        logger.error(f"Error creating prediction: {error_text}")
                        return None
                    
                    prediction = await response.json()
                    prediction_id = prediction.get('id')
                    logger.info(f"WAN prediction created with ID: {prediction_id}")
                    
                    # Poll for completion
                    return await self._poll_prediction(session, prediction_id, headers)
                    
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return None
        except Exception as e:
            logger.error(f"Error in generate_wan_lora_video: {str(e)}", exc_info=True)
            return None

    async def generate_kling_lipsync(self, video_path: str, audio_path: str) -> str | None:
        """Generate lipsynced video using Kling Lip Sync model (slower, high quality).
        
        Args:
            video_path: Path to source video file
            audio_path: Path to audio file for lipsync
            
        Returns:
            URL to lipsynced video, or None if failed
        """
        logger.info(f"Generating Kling lipsync with video: {video_path}, audio: {audio_path}")
        
        try:
            # Use replicate client library which handles file uploads and returns URLs
            with open(video_path, "rb") as video_file, open(audio_path, "rb") as audio_file:
                output = await asyncio.to_thread(
                    self.replicate_client.run,
                    "kwaivgi/kling-lip-sync",
                    input={
                        "video_url": video_file,  # Library auto-uploads and converts to URL
                        "audio_url": audio_file   # Changed from 'audio' to 'audio_url'
                    }
                )
                logger.info(f"Kling lipsync successful. Output: {output}")
                # Output could be string or list
                if isinstance(output, list) and len(output) > 0:
                    return output[0]
                return output
                
        except replicate.exceptions.ReplicateError as e:
            logger.error(f"Replicate API error during Kling lipsync: {e}")
            return None
        except FileNotFoundError as e:
            logger.error(f"File not found for Kling lipsync: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in generate_kling_lipsync: {e}", exc_info=True)
            return None

    async def generate_pixverse_lipsync(self, video_path: str, audio_path: str) -> str | None:
        """Generate lipsynced video using Pixverse Lipsync model (fast).
        
        Args:
            video_path: Path to source video file
            audio_path: Path to audio file for lipsync
            
        Returns:
            URL to lipsynced video, or None if failed
        """
        logger.info(f"Generating Pixverse lipsync with video: {video_path}, audio: {audio_path}")
        
        try:
            with open(video_path, "rb") as video_file, open(audio_path, "rb") as audio_file:
                input_data = {
                    "video": video_file,
                    "audio": audio_file
                }
                output = await asyncio.to_thread(
                    self.replicate_client.run,
                    "pixverse/lipsync",
                    input=input_data
                )
                logger.info(f"Pixverse lipsync successful. Output: {output}")
                # Output could be string or list
                if isinstance(output, list) and len(output) > 0:
                    return output[0]
                return output
                
        except replicate.exceptions.ReplicateError as e:
            logger.error(f"Replicate API error during Pixverse lipsync: {e}")
            return None
        except FileNotFoundError as e:
            logger.error(f"File not found for Pixverse lipsync: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in generate_pixverse_lipsync: {e}", exc_info=True)
            return None
