# scene_manager.py
import os
import aiohttp
import base64
import io
from PIL import Image
from datetime import datetime
import logging
from typing import Dict, Optional # Import Dict and Optional
from config import (
    STABLE_DIFFUSION_URL,
    OPENROUTER_KEY,
    STABLE_DIFFUSION_SCENE_SETTINGS,
    OPENROUTER_URL, OPENROUTER_HEADERS,
    OPENAI_API_KEY, OPENAI_HEADERS, OPENAI_IMAGE_GENERATION_URL,
    OPENAI_IMAGE_EDIT_URL, OPENAI_IMAGE_MODELS # Added OpenAI configs
)
from gamemasters import gamemasters
import aiohttp
import asyncio # For potential future async operations with files

# Set up logging
logger = logging.getLogger(__name__)

# Helper to find character names (simple placeholder)
def find_characters_in_prompt(prompt: str, known_characters: list) -> list:
    """Placeholder function to identify known characters mentioned in a prompt."""
    found = []
    prompt_lower = prompt.lower()
    for char_name in known_characters:
        if char_name.lower() in prompt_lower:
            found.append(char_name)
    logger.info(f"Found characters in prompt: {found}")
    return found

class SceneManager:
    def __init__(self, adventure_manager, gamemaster_name, media_model=None, image_generation_service="Stable Diffusion (Local)"):
        self.adventure_manager = adventure_manager
        self.gamemaster_name = gamemaster_name
        self.image_prompt_guidance = gamemasters[gamemaster_name].get("image_prompt", "Generate detailed scene descriptions.")

        # Model for PROMPT generation (via OpenRouter)
        if not media_model:
             self.prompt_generation_model = "cohere/command-r-plus-04-2024" # Default prompt gen model
             logger.warning(f"No media_model provided for prompt generation, defaulting to {self.prompt_generation_model}")
        else:
             # TODO: Validate if the provided media_model is actually an OpenRouter model?
             self.prompt_generation_model = media_model

        # Service for FINAL image generation
        self.image_generation_service = image_generation_service
        # Model for FINAL image generation (relevant if service is OpenAI)
        # We might need to pass the specific image model selected in launcher if using OpenAI
        # For now, assume config holds the default if service is OpenAI
        self.image_generation_model = OPENAI_IMAGE_MODELS.get("gpt-image-1", "gpt-image-1") # Default to gpt-image-1 if OpenAI service

        # State for consistency (only relevant for OpenAI service)
        self.character_references: Dict[str, str] = {} # name -> b64_json image data
        self.current_scene_image_data: Optional[str] = None # b64_json image data

        logger.info(f"SceneManager initialized for GM '{gamemaster_name}'")
        logger.info(f"Using prompt generation model (OpenRouter): {self.prompt_generation_model}")
        logger.info(f"Using image generation service: {self.image_generation_service}")
        if self.image_generation_service == "OpenAI":
             logger.info(f"Using OpenAI image model: {self.image_generation_model}")


    async def generate_scene_prompt(self, conversation, prompt_mode="direct"):
        """
        Generate a scene description prompt based on the current game state.
        
        prompt_mode options:
        - "direct": Use italicized text directly from GM's response
        - "generate": Generate new prompt from conversation context
        - "enhance": Use italicized text as input to generate enhanced prompt
        """
        logger.info(f"Generating scene prompt using mode: {prompt_mode}")

        if not conversation: # Check if conversation is None or empty
            logger.warning("No conversation history available or conversation is None")
            return None

        # Log conversation details
        logger.info(f"Conversation length: {len(conversation)}")
        for i, msg in enumerate(conversation):
            logger.info(f"Message {i}: role={msg['role']}")
            logger.info(f"Message {i} content: {msg['content']}")

        # Get GM messages
        gm_messages = [msg["content"] for msg in conversation if msg["role"] == "assistant"]
        logger.info(f"Found {len(gm_messages)} GM messages")
        
        # Get last message (current scene)
        current_scene = gm_messages[-1] if gm_messages else ""
        logger.info(f"Current scene content (full):\n{current_scene}")
        
        # Extract the italicized scene description if it exists (last set of asterisks)
        import re
        pattern = r'\*([^*]*)\*(?![^*]*\*)'  # Matches last set of asterisks
        scene_match = re.search(pattern, current_scene)
        logger.info(f"Searching for pattern: {pattern}")
        logger.info(f"Regex match success: {scene_match is not None}")
        
        if scene_match:
            captured_text = scene_match.group(1)
            logger.info(f"Captured text between asterisks: {captured_text}")
            if not captured_text.strip():
                logger.warning("Captured text is empty after stripping whitespace")
        
        if prompt_mode == "direct":
            if scene_match:
                scene_prompt = scene_match.group(1).strip()
                if scene_prompt:
                    logger.info(f"Using existing scene description: {scene_prompt}")
                    return scene_prompt
                else:
                    logger.warning("Found asterisks but no content between them")
                    return None
            logger.warning("No italicized text found in direct mode")
            return None
            
        elif prompt_mode == "generate":
            # Generate new prompt from recent conversation context
            context = f"""
            Based on this scene description from a text adventure game:
            {current_scene}

            Generate a detailed image prompt for Stable Diffusion that captures the current scene.
            Focus on the environment, lighting, atmosphere, and any notable objects or characters.
            The prompt should be descriptive and specific, suitable for image generation.
            
            ONLY generate the prompt itself, avoid any commentary or explanation.
            """
            
        elif prompt_mode == "enhance":
            if not scene_match:
                logger.warning("No italicized text found to enhance")
                return None
                
            base_prompt = scene_match.group(1)
            context = f"""
            Enhance this scene description for Stable Diffusion image generation:
            {base_prompt}

            Add more details about:
            - Lighting and atmosphere
            - Materials and textures
            - Camera perspective
            - Important objects and characters
            
            ONLY generate the enhanced prompt itself, avoid any commentary or explanation.
            """
            
        else:
            logger.error(f"Invalid prompt mode: {prompt_mode}")
            return None

        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates scene description prompts for image generation."},
            {"role": "user", "content": context}
        ]

        headers = OPENROUTER_HEADERS.copy()
        logger.info(f"Making API call to {self.prompt_generation_model} for {prompt_mode} mode") # Use dedicated model

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENROUTER_URL, # Assuming prompt generation always uses OpenRouter for now
                json={
                    "model": self.prompt_generation_model, # Use dedicated model
                    "temperature": 0.5,
                    "max_tokens": 150, # Slightly increased max tokens for potentially more detailed prompts
                    "messages": messages
                },
                headers=headers
            ) as response:
                response_json = await response.json()
                if 'choices' in response_json and len(response_json['choices']) > 0:
                    scene_prompt = response_json['choices'][0]['message']['content']
                    logger.info(f"Generated scene prompt ({prompt_mode} mode):\n{scene_prompt}")
                    return scene_prompt
                else:
                    logger.error(f"Failed to generate scene prompt. Response: {response_json}")
                    return None

    # --- Character Reference Management (for OpenAI) ---
    async def generate_character_reference(self, character_name: str, description: str):
        """Generates and stores a reference image for a character using OpenAI."""
        if self.image_generation_service != "OpenAI":
            logger.warning("Character reference generation only supported for OpenAI image service.")
            return

        # Simple prompt focusing on the character
        prompt = f"Detailed character concept art for {character_name}, described as: {description}. Neutral background, clear view."
        logger.info(f"Generating reference image for {character_name} using OpenAI...")

        # Use the specific OpenAI generation method
        image_data = await self._call_openai_generations(prompt, size="1024x1024")

        if image_data:
            self.character_references[character_name] = image_data
            logger.info(f"Stored reference image for {character_name}")
            # Optionally save the reference image separately
            # await self.save_image(image_data, f"ref_{character_name}")
        else:
            logger.error(f"Failed to generate reference image for {character_name}")


    # --- Main Image Generation Logic ---
    async def generate_image(self, prompt: str, player_action: Optional[str] = None, gm_outcome: Optional[str] = None):
        """
        Generate an image using the selected image generation service.
        Optionally accepts player_action and gm_outcome for context, primarily for OpenAI edits.
        """
        if not prompt:
            logger.error("Cannot generate image: prompt is empty.")
            return None

        # Switch based on the selected service
        if self.image_generation_service == "OpenAI":
            # Update log to show the actual model being used in the API call
            logger.info(f"Generating image using OpenAI (gpt-image-1)...")
            logger.info(f"[OpenAI Image Prompt] {prompt}")
            # Call the internal OpenAI handler, passing context
            image_data = await self._generate_openai_image(prompt, player_action, gm_outcome)
            # Update scene state *after* successful generation
            if image_data:
                 self.current_scene_image_data = image_data
            return image_data

        elif self.image_generation_service == "Stable Diffusion (Local)":
            logger.info("Generating image using Stable Diffusion (Local)...")
            logger.info(f"\033[92m[Stable Diffusion Prompt] {prompt}\033[0m")
            payload = {
                "prompt": prompt,
                **STABLE_DIFFUSION_SCENE_SETTINGS # Correctly unpack inside the dict
            }
            async with aiohttp.ClientSession() as session:
                try:
                    # Correctly indented block under try
                    async with session.post(STABLE_DIFFUSION_URL, json=payload) as response:
                        if response.status == 200:
                            r = await response.json()
                            if 'images' in r and len(r['images']) > 0:
                                # SD returns base64 string directly in 'images' list
                                return r['images'][0]
                        else:
                            logger.error(f"Stable Diffusion API error: Status {response.status} - {await response.text()}")
                            return None
                # Correctly indented except block
                except aiohttp.ClientConnectorError as e:
                    # Correctly indented code under except
                    logger.error(f"Could not connect to Stable Diffusion API at {STABLE_DIFFUSION_URL}: {e}")
                    return None
        else:
             logger.error(f"Unsupported image generation service: {self.image_generation_service}")
             return None


    # --- OpenAI Specific Methods (Re-added) ---
    async def _generate_openai_image(self, prompt: str, player_action: Optional[str] = None, gm_outcome: Optional[str] = None):
        """Handles OpenAI image generation/editing logic for consistency."""
        # Determine if it's an initial scene or update
        is_update = self.current_scene_image_data is not None

        # Identify characters mentioned in the current prompt
        present_characters = find_characters_in_prompt(prompt, list(self.character_references.keys()))

        # Use edit if a previous scene image exists
        if is_update:
            logger.info("Attempting OpenAI image edit for scene consistency...")
            # Prepare image inputs - always include the scene
            image_inputs = {'scene': self.current_scene_image_data}
            # Add character references IF they exist
            chars_with_refs_found = []
            for char_name in present_characters:
                if char_name in self.character_references:
                    image_inputs[char_name] = self.character_references[char_name]
                    chars_with_refs_found.append(char_name)
                else:
                     logger.warning(f"Character '{char_name}' mentioned in prompt but no reference image found in storage.")

            # Construct the edit prompt with consistency instructions AND action context
            consistency_instruction = "Edit the base scene image provided (first input image)."
            if chars_with_refs_found:
                 consistency_instruction += f" Maintain consistency for the characters ({', '.join(chars_with_refs_found)}) based on their provided reference images (subsequent input images)."

            # Add context about the last action/outcome
            action_context = ""
            if player_action:
                 action_context += f" The player's last action was: '{player_action}'."
            if gm_outcome:
                 # Maybe truncate gm_outcome if too long?
                 outcome_snippet = (gm_outcome[:200] + '...') if len(gm_outcome) > 200 else gm_outcome
                 action_context += f" The immediate result described was: '{outcome_snippet}'."

            # Combine instructions, context, and the target scene description
            edit_prompt = f"{consistency_instruction}{action_context} Update the image to reflect the following scene state: {prompt}"

            logger.info(f"Using edit prompt: {edit_prompt}")
            logger.info(f"Providing {len(image_inputs)} images to edit endpoint: {list(image_inputs.keys())}")

            return await self._call_openai_edits(edit_prompt, image_inputs)
        else:
            # Generate a new image if no previous scene exists
            logger.info("Generating new OpenAI image (initial scene)...")
            # Reset scene data just in case (should be None already)
            self.current_scene_image_data = None
            return await self._call_openai_generations(prompt)

    async def _call_openai_generations(self, prompt: str, size: str = "1024x1024", n: int = 1):
        """Calls the OpenAI v1/images/generations endpoint."""
        payload = {
            "model": "gpt-image-1", # Hardcode correct model name for now
            "prompt": prompt,
            "n": n,
            "size": size,
            # Removed "response_format": "b64_json" as it's not supported for gpt-image-1
        }
        headers = OPENAI_HEADERS.copy()

        logger.debug(f"Calling OpenAI Generations API: {OPENAI_IMAGE_GENERATION_URL}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(OPENAI_IMAGE_GENERATION_URL, json=payload, headers=headers) as response:
                    if response.status == 200:
                        r = await response.json()
                        if r.get('data') and len(r['data']) > 0 and r['data'][0].get('b64_json'):
                            logger.info("OpenAI Generations successful.")
                            return r['data'][0]['b64_json']
                        else:
                            logger.error(f"OpenAI Generations API error: Unexpected response format - {r}")
                            return None
                    else:
                        logger.error(f"OpenAI Generations API error: Status {response.status} - {await response.text()}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Error calling OpenAI Generations API: {e}")
                return None

    async def _call_openai_edits(self, prompt: str, image_inputs: Dict[str, str], size: str = "1024x1024", n: int = 1):
        """Calls the OpenAI v1/images/edits endpoint with multiple images."""
        # Ensure the model supports edits (gpt-image-1 does)
        # We are hardcoding gpt-image-1 for now, so this check is less critical but kept for future use
        # if self.image_generation_model != "gpt-image-1":
        #      logger.warning(f"Image editing/multi-image input might not be supported by model {self.image_generation_model}. Trying anyway.")

        headers = OPENAI_HEADERS.copy()
        headers.pop('Content-Type', None) # Let aiohttp set multipart header

        data = aiohttp.FormData()
        data.add_field('prompt', prompt)
        data.add_field('model', "gpt-image-1") # Hardcode correct model name for now
        data.add_field('n', str(n))
        data.add_field('size', size)
        # Removed 'response_format' as it's not supported for gpt-image-1 edits

        # Add images (ensure scene image is first if order matters)
        if 'scene' in image_inputs:
             try:
                  image_bytes = base64.b64decode(image_inputs['scene'])
                  data.add_field('image', image_bytes, filename='scene.png', content_type='image/png')
             except (TypeError, ValueError) as e:
                  logger.error(f"Error decoding base64 scene image data: {e}")
                  return None
        else:
             logger.error("Scene image data missing for edit call.")
             return None # Cannot edit without base scene

        for name, b64_data in image_inputs.items():
            if name == 'scene': continue # Already added
            try:
                image_bytes = base64.b64decode(b64_data)
                filename = f"{name.replace(' ', '_')}_ref.png"
                data.add_field('image', image_bytes, filename=filename, content_type='image/png')
            except (TypeError, ValueError) as e:
                logger.error(f"Error decoding base64 image data for {name}: {e}")
                # Optionally continue without this reference? Or fail? Failing is safer.
                return None

        logger.debug(f"Calling OpenAI Edits API: {OPENAI_IMAGE_EDIT_URL}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(OPENAI_IMAGE_EDIT_URL, data=data, headers=headers) as response:
                    if response.status == 200:
                        r = await response.json()
                        if r.get('data') and len(r['data']) > 0 and r['data'][0].get('b64_json'):
                            logger.info("OpenAI Edits successful.")
                            return r['data'][0]['b64_json']
                        else:
                            logger.error(f"OpenAI Edits API error: Unexpected response format - {r}")
                            return None
                    else:
                        logger.error(f"OpenAI Edits API error: Status {response.status} - {await response.text()}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Error calling OpenAI Edits API: {e}")
                return None


    # --- Image Saving ---
    async def save_image(self, image_data: str, base_filename: str = "scene"):
        """Save the generated image (base64 string) to the current adventure's output directory."""
        if not image_data:
            logger.error("Cannot save image: image_data is None or empty.")
            return None
        try:
            # Decode base64 string (handles potential data URI prefix)
            if "," in image_data:
                img_b64 = image_data.split(",", 1)[1]
            else:
                img_b64 = image_data
            image_bytes = base64.b64decode(img_b64)
            image = Image.open(io.BytesIO(image_bytes))

            # Ensure image is RGB before saving as PNG to avoid potential issues
            if image.mode != 'RGB':
                image = image.convert('RGB')

        except Exception as e:
            logger.error(f"Error decoding or opening image data: {e}")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_file_name = f"{base_filename}_{timestamp}.png" # Use base_filename
        image_file_path = os.path.join(self.adventure_manager.subfolder_path, image_file_name)
        image.save(image_file_path)
        return image_file_path
