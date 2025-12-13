import os
import re
import logging
import aiohttp
import base64
import io
from PIL import Image
from datetime import datetime
from config import (
    STABLE_DIFFUSION_URL, 
    OPENROUTER_KEY, 
    INSIGHTFACE_MODEL_PATH,
    IMAGE_WIDTH,
    IMAGE_HEIGHT,
    IMAGE_STEPS,
    IMAGE_GUIDANCE_SCALE,
    IMAGE_SAMPLER,
    DEFAULT_SD_MODEL,
    LUMINA_SD_MODEL,
    LUMINA_VAE,
    LUMINA_TEXT_ENCODER,
    LUMINA_SAMPLER,
    LUMINA_SCHEDULER,
    LUMINA_STEPS,
    LUMINA_CFG_SCALE,
    LUMINA_SHIFT
)
from characters import characters

logger = logging.getLogger(__name__)

class ImageManager:
    def __init__(self, conversation_manager, character_name, api_manager):
        self.conversation_manager = conversation_manager
        self.character_name = character_name
        self.api_manager = api_manager # Store api_manager instance
        self.image_prompt = characters[character_name]["image_prompt"]
        self.source_faces_folder = characters[character_name]["source_faces_folder"]

    async def generate_selfie_prompt(self, conversation, pov_mode=False, first_person_mode=False):
        ethnicity_match = re.search(r'\b(?:\d+(?:-year-old)?[\s-]?)?(?:asian|lebanese|black|african|caucasian|white|hispanic|latino|latina|mexican|european|middle eastern|indian|native american|pacific islander|mixed race|biracial|multiracial|[^\s]+?(?=\s+(?:girl|woman|lady|female|man|guy|male|dude)))\b', self.image_prompt, re.IGNORECASE)
        if ethnicity_match:
            ethnicity = ethnicity_match.group()
        else:
            ethnicity = "unknown ethnicity"

        context = ""
        if len(conversation) > 0:
            # Get bot messages
            bot_messages = [msg["content"] for msg in conversation if msg["role"] == "assistant"]

            # Get only the last message (if any)
            if bot_messages:
                last_bot_message = bot_messages[-1]
                logger.info("Generating image prompt using the last bot message")
                logger.debug(f"Message preview: {last_bot_message[:200]}...")

                # Build the context string without using complex f-strings
                context = "Based on the following section from a text adventure game:\n"
                context += last_bot_message
                context += "\n\nUse the information in the following text:\n"
                context += self.image_prompt
                context += f"\n\nGenerate a detailed image prompt for Stable Diffusion to create a photo of the character in this conversation, considering their ethnicity: {ethnicity}."
            else:
                # Handle case where there are no bot messages yet
                logger.info("No bot messages found, generating prompt based on character description only")
                context = "Use the information in the following text:\n"
                context += self.image_prompt
                context += f"\n\nGenerate a detailed image prompt for Stable Diffusion to create a photo of the character in this conversation, considering their ethnicity: {ethnicity}."


            # Add the prompt format instructions based on mode
            if first_person_mode:
                # Override context to ignore character description if in first person mode
                # We want the SCENE, not the character
                context += """
                The prompt should follow this format:

                cinematic shot, raw photo, first-person view of <describe the scene/action from the user's eyes>, <mood/lighting>, <environment details>, realistic, 8k, high quality

                IMPORTANT:
                - This is a FIRST-PERSON view (POV) of the player.
                - DO NOT describe the character defined in the text unless they are explicitly in the scene.
                - Focus on what the player is seeing (hands, environment, objects, other people).
                - If the character is present, describe them naturally in the scene.
                - If the character is NOT present (e.g. player is alone), describe the environment.

                <EXAMPLES>
                cinematic shot, raw photo, first-person view of walking through a dark forest, holding a flashlight, tall trees, fog, eerie atmosphere, realistic, 8k

                cinematic shot, raw photo, first-person view of sitting at a desk looking at a computer screen, hands on keyboard, coffee mug on table, dim lighting, realistic, 8k

                cinematic shot, raw photo, first-person view of looking at a woman standing in the doorway, warm lighting, cozy home atmosphere, realistic, 8k

                ONLY generate the prompt itself, avoid narrating or commenting.
                DO NOT use terms like 'handheld phone photo' or 'selfie'.
                """
            elif pov_mode:
                context += """
                The prompt should follow this format (change <these parts> to suit the context of the conversation and how the character looks in a photo now):

                cinematic shot, raw photo, first-person view of <describe the character, e.g. 'a 20-year-old asian girl'> <describe what they're wearing and what they're doing', e.g. 'sitting across the table holding a coffee cup'>, <describe the place, e.g. 'in a cozy cafe'>, <mood/lighting>, looking at viewer (if interacting) OR looking away (if described)

                MAKE SURE to extract where she is from the text, and include that background in the prompt, AND ALSO describe what she's doing according to the text.

                <EXAMPLES>
                cinematic shot, raw photo, first-person view of a young american girl wearing a hoodie and glasses sitting on the bed, looking up at viewer with a smile, dark room, warm lamp light, cozy atmosphere, high quality, 8k

                cinematic shot, raw photo, first-person view of a young asian girl wearing a suit and pencil skirt standing in front of the bathroom mirror applying makeup, looking at reflection, bright bathroom lighting, sharp focus, detailed

                cinematic shot, raw photo, first-person view of an asian woman wearing a summer dress walking away down the beach, turning back to look at viewer, sunset lighting, golden hour, wind blowing hair, romantic atmosphere

                ONLY generate the prompt itself, avoid narrating or commenting, just write the short descriptive prompt.
                DO NOT use terms like 'handheld phone photo', 'selfie', or 'holding camera'.
                Focus on the immersive atmosphere and the character's interaction with the observer (the camera).

                ALWAYS indicate what she's wearing in the photo, top and bottom, and where she is based on context.
                ALWAYS prioritize the latter part of the context to describe her body position and what she's doing. use the earlier context mostly for deducing the setting."""
            else:
                # Default Selfie Mode
                context += """
                The prompt should follow this format (change <these parts> to suit the context of the conversation and how the character looks in a photo now):

                handheld amateur phone photo, pov shot of <describe the character, e.g. 'a 20-year-old asian girl'> <describe what they're wearing and what they're doing', e.g. 'wearing a bikini and lying on a bed with her arms stretched out'>, <describe the place, e.g. 'in a messy bedroom'>, looking at viewer

                MAKE SURE to extract where she is from the text, and include that background in the webcam photo prompt, AND ALSO describe what she's doing according to the text.

                <EXAMPLES>
                handheld amateur phone photo, pov shot of a young american girl wearing a hoodie and glasses under the covers, looking up at viewer, dark room, grainy, candid, gritty, blurry, low quality, flash photography

                handheld amateur phone photo, pov shot of a young asian girl wearing a a suit and pencil skirt while holding a pen and bending over in front of the bathroom mirror, looking at viewer, grainy, candid, gritty, blurry, low quality, flash photography

                handheld amateur phone photo, pov shot of an asian woman wearing a thong and tank top posing seductively in a dorm room, holding up her hands in surprise, looking at viewer, dark room, grainy, candid, gritty, blurry, low quality, flash photography

                ONLY generate the prompt itself, avoid narrating or commenting, just write the short descriptive prompt.

                ALWAYS indicate what she's wearing in the photo, top and bottom, and where she is based on context.

                ALWAYS prioritize the latter part of the context to describe her body position and what she's doing.  use the earlier context mostly for deducing the setting."""

        system_prompt = "You are a helpful assistant that generates image prompts."
        user_prompt = "{image_generation_prompt}\n" + context

        # Use the configured media LLM instead of hardcoded Grok
        image_prompt = await self.api_manager.generate_media_llm_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.5
        )

        if image_prompt:
            logger.info(f"Generated selfie prompt from media LLM: {image_prompt}")
            return image_prompt
        else:
            logger.error("Failed to get prompt from media LLM")
            return None

    async def generate_image(self, prompt, first_person_mode=False, sd_mode="xl"):
        # Determine if we should use ReActor (Face Swap)
        # If first_person_mode is True, we DISABLE ReActor because we want a generic/scene view, not the character's face
        use_reactor = not first_person_mode
        
        reactor_args = [
            None,  # Placeholder for img_base64
            use_reactor,  # Enable ReActor
            '0',  # Comma separated face number(s) from swap-source image
            '0',  # Comma separated face number(s) for target image (result)
            INSIGHTFACE_MODEL_PATH,  # Model path
            'CodeFormer',  # Restore Face: None; CodeFormer; GFPGAN
            1,  # Restore visibility value
            True,  # Restore face -> Upscale
            'None',  # Upscaler (type 'None' if doesn't need)
            1.5,  # Upscaler scale value
            1,  # Upscaler visibility (if scale = 1)
            False,  # Swap in source image
            True,  # Swap in generated image
            1,  # Console Log Level (0 - min, 1 - med or 2 - max)
            0,  # Gender Detection (Source) (0 - No, 1 - Female Only, 2 - Male Only)
            0,  # Gender Detection (Target) (0 - No, 1 - Female Only, 2 - Male Only)
            False,  # Save the original image(s) made before swapping
            0.5,  # CodeFormer Weight (0 = maximum effect, 1 = minimum effect), 0.5 - by default
            False,  # Source Image Hash Check, True - by default
            False,  # Target Image Hash Check, False - by default
            "CUDA",  # CPU or CUDA (if you have it), CPU - by default
            True,  # Face Mask Correction
            2,  # Select Source, 0 - Image, 1 - Face Model, 2 - Source Folder
            "elena.safetensors",  # Filename of the face model (from "models/reactor/faces"), e.g. elena.safetensors, don't forget to set #22 to 1
            self.source_faces_folder,  # The path to the folder containing source faces images, don't forget to set #22 to 2
            None,  # skip it for API
            True,  # Randomly select an image from the path
            True,  # Force Upscale even if no face found
            0.6,  # Face Detection Threshold
            2,  # Maximum number of faces to detect (0 is unlimited)
        ]

        # Build payload based on SD mode
        logger.info(f"[DEBUG] generate_image received sd_mode='{sd_mode}' (type: {type(sd_mode).__name__})")
        if sd_mode == "lumina":
            # Lumina mode: different model, VAE, sampler, scheduler, steps, CFG, and shift
            # Model and VAE must be in override_settings for Forge to actually load them
            payload = {
                "prompt": prompt,
                "steps": LUMINA_STEPS,
                "sampler_name": LUMINA_SAMPLER,
                "scheduler": LUMINA_SCHEDULER,
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "seed": -1,
                "cfg_scale": LUMINA_CFG_SCALE,
                "alwayson_scripts": {"reactor": {"args": reactor_args}},
                # Model, VAE, and text encoder in override_settings
                # GGUF models are smaller, so no memory overrides needed - use Forge defaults
                "override_settings": {
                    "sd_model_checkpoint": LUMINA_SD_MODEL,
                    "sd_vae": LUMINA_VAE,
                    "forge_additional_modules": [
                        f"C:\\AI\\ForgeUI\\models\\VAE\\{LUMINA_VAE}",
                        f"C:\\AI\\ForgeUI\\models\\text_encoder\\{LUMINA_TEXT_ENCODER}"
                    ]
                }
            }
            logger.info(f"Using Lumina mode for image generation")
        else:
            # XL mode (default): standard SDXL settings
            # Model settings in override_settings to ensure proper switching from Lumina
            payload = {
                "prompt": prompt,
                "steps": IMAGE_STEPS,
                "sampler_name": IMAGE_SAMPLER,
                "scheduler": "Karras",
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "seed": -1,
                "cfg_scale": IMAGE_GUIDANCE_SCALE,
                "alwayson_scripts": {"reactor": {"args": reactor_args}},
                # Only include model settings to ensure switching from Lumina works
                # Let Forge use its startup defaults for memory/performance settings
                "override_settings": {
                    "sd_model_checkpoint": DEFAULT_SD_MODEL,
                    "sd_vae": "Automatic",
                    "forge_additional_modules": [],
                    "CLIP_stop_at_last_layers": 2
                }
            }
            logger.info(f"Using XL mode for image generation")

        logger.info(f"Sending payload to Stable Diffusion: {payload}")

        async with aiohttp.ClientSession() as session:
            async with session.post(STABLE_DIFFUSION_URL, json=payload, headers={'Content-Type': 'application/json'}) as response:
                if response.status == 200:
                    r = await response.json()
                    if 'images' in r and len(r['images']) > 0:
                        image_data = r['images'][0]
                        return image_data
                    else:
                        return None
                else:
                    return None

    async def save_image(self, image_data):
        image = Image.open(io.BytesIO(base64.b64decode(image_data.split(",", 1)[0])))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_file_name = f"selfie_image_{timestamp}.png"
        image_file_path = os.path.join(self.conversation_manager.subfolder_path, image_file_name)
        image.save(image_file_path)
        return image_file_path

    async def generate_wan_video_prompt(self, conversation):
        """Generates a simple action prompt for the WAN video model based on recent conversation."""
        context = ""
        if len(conversation) > 0:
            # Get last 3 messages (user and assistant)
            recent_messages = conversation[-3:] if len(conversation) >= 3 else conversation
            combined_context = "\n".join([f'{msg["role"]}: {msg["content"]}' for msg in recent_messages])

            logger.info(f"\nGenerating WAN video prompt using {len(recent_messages)} messages:")
            for i, msg in enumerate(recent_messages, 1):
                logger.info(f"\nMessage {i} ({msg['role']}):\n{msg['content'][:200]}...")

            # Detailed prompt asking the LLM to describe the character's action and emotion
            system_prompt_for_action = """Analyze the last few messages of the conversation provided below. Based on the conversation context, describe the character's current action, facial expression, and emotional state for a video generation prompt.

Focus on:
1. The physical action (e.g., sitting, walking, laughing).
2. The facial expression and emotion (e.g., smiling warmly, looking concerned, laughing uncontrollably, crying).
3. Any subtle movements (e.g., tilting head, hand gestures).

Conversation Context:
{context}

Output a single descriptive sentence starting with "A woman is...".
Example: "A woman is sitting on a couch laughing hysterically with her head thrown back."
Example: "A woman is standing by the window looking wistful and sad while touching the glass."
"""

            prompt_content = system_prompt_for_action.format(context=combined_context)

        else:
            # Default prompt if no conversation history
            prompt_content = "A woman is standing still looking at the camera."
            system_prompt_for_action = "Output the phrase 'A woman is standing still looking at the camera.'."

        # Use the APIManager's media LLM generation method
        try:
            action_prompt = await self.api_manager.generate_media_llm_response(
                system_prompt=system_prompt_for_action,
                user_prompt=prompt_content, # Pass the context-based prompt here
                max_tokens=100,
                temperature=0.7
            )

            if action_prompt:
                # Basic validation/cleanup
                final_prompt = action_prompt.strip()
                # Ensure it starts with "A woman is" if the LLM messed up, though the prompt asks for it.
                if not final_prompt.lower().startswith("a woman"):
                     final_prompt = f"A woman is {final_prompt}"
                
                logger.info(f"\nGenerated WAN video prompt: {final_prompt}")
                return final_prompt
            else:
                logger.error(f"Error generating WAN prompt: Media LLM returned None")
                return "A woman is talking expressively" # Fallback prompt
        except Exception as e:
            logger.error(f"Exception generating WAN prompt: {e}", exc_info=True)
            return "A woman is talking expressively" # Fallback prompt

    async def generate_video_prompt(self, conversation):
        ethnicity_match = re.search(r'\b(?:\d+(?:-year-old)?[\s-]?)?(?:asian|lebanese|black|african|caucasian|white|hispanic|latino|latina|mexican|european|middle eastern|indian|native american|pacific islander|mixed race|biracial|multiracial|[^\s]+?(?=\s+(?:girl|woman|lady|female|man|guy|male|dude)))\b', self.image_prompt, re.IGNORECASE)
        if ethnicity_match:
            ethnicity = ethnicity_match.group()
        else:
            ethnicity = "unknown ethnicity"

        context = ""
        if len(conversation) > 0:
            # Get bot messages
            bot_messages = [msg["content"] for msg in conversation if msg["role"] == "assistant"]
            # Get last 3 messages (or all if less than 3)
            bot_messages = bot_messages[-3:] if len(bot_messages) >= 3 else bot_messages
            combined_context = "\n".join(bot_messages)
            
            logger.info(f"Generating video prompt using {len(bot_messages)} bot messages")
            for i, msg in enumerate(bot_messages, 1):
                logger.debug(f"Message {i} preview: {msg[:200]}...")
            context = f"""
            Based on the following conversation:\n{combined_context}\n\n and this character description:\n{self.image_prompt}\n\nGenerate a short, descriptive video generation prompt to create an animated video of the character, considering their ethnicity: {ethnicity}.
            
            The prompt should follow this format:
            A [age] [ethnicity] [gender] with [physical features], [expression/emotion] while talking, [head/body position], how she's moving and what her body is doing [lighting/atmosphere], [background/setting]
            
            EXAMPLES:
            A 24-year-old asian woman with long black hair and soft features, speaking expressively with a slight smile, head tilted slightly, shifting in her seat while she crosses her legs, warm indoor lighting, cozy bedroom setting
            
            A young caucasian woman with blonde hair and bright eyes, talking animatedly with changing expressions, as she's walking around her apartent and looking in the mirror, casual head movements, natural daylight from window, modern apartment interior
            
            IMPORTANT:
            - Focus on facial features and expressions, as well as body language, since this is for a video
            - Include natural head movements and expression changes
            - Include body movements, and prompting about how the character is moving and activities she's doing.
            - Describe the lighting and atmosphere that matches the conversation mood, and anything moving in the background.
            - Keep it a short, descriptive video prompt for a video generator AI.
            
            ONLY generate the prompt itself, no commentary or explanations."""

        prompt = f"{{video_generation_prompt}}\n{context}"
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates video prompts."},
            {"role": "user", "content": prompt}
        ]

        api_url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "HTTP-Referer": "https://discord.com/api/oauth2/authorize?client_id=1139328683987980288&permissions=1084479764544&scope=bot",
            "X-Title": "my-discord-bot",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json={"model": "x-ai/grok-3-beta", "temperature": 0.5, "max_tokens": 128, "messages": messages}, headers=headers) as response:
                response_json = await response.json()
                if 'choices' in response_json and len(response_json['choices']) > 0:
                    video_prompt = response_json['choices'][0]['message']['content']
                    logger.info(f"Generated video prompt: {video_prompt}")
                    return video_prompt
                else:
                    return None
