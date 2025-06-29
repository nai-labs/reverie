# image_manager.py
import os
import re
import aiohttp
import base64
import io
import logging # Added logging
from PIL import Image
from datetime import datetime
from config import STABLE_DIFFUSION_URL, OPENROUTER_KEY, INSIGHTFACE_MODEL_PATH
from characters import characters
import discord

logger = logging.getLogger(__name__) # Added logger

class ImageManager:
    # Modified __init__ to accept api_manager
    def __init__(self, conversation_manager, character_name, api_manager):
        self.conversation_manager = conversation_manager
        self.character_name = character_name
        self.api_manager = api_manager # Store api_manager instance
        self.image_prompt = characters[character_name]["image_prompt"]
        self.source_faces_folder = characters[character_name]["source_faces_folder"]

    async def generate_selfie_prompt(self, conversation):
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
                print(f"\nGenerating image prompt using the last bot message:")
                print(f"\nMessage:\n{last_bot_message[:200]}...")  # Print first 200 chars of each message
                
                # Build the context string without using complex f-strings
                context = "Based on the following section from a text adventure game:\n"
                context += last_bot_message
                context += "\n\nUse the information in the following text:\n"
                context += self.image_prompt
                context += f"\n\nGenerate a detailed image prompt for Stable Diffusion to create a photo of the character in this conversation, considering their ethnicity: {ethnicity}."
            else:
                # Handle case where there are no bot messages yet
                print("\nNo bot messages found, generating prompt based on character description only.")
                context = "Use the information in the following text:\n"
                context += self.image_prompt
                context += f"\n\nGenerate a detailed image prompt for Stable Diffusion to create a photo of the character described, considering their ethnicity: {ethnicity}."
            
            # Add the prompt format instructions
            context += """
            The prompt should follow this format (change <these parts> to suit the context of the conversation and how the character looks in a photo now):
            
            webcam photo of <describe the character, e.g. 'a 20-year-old asian girl'> <describe what they're wearing and what they're doing', e.g. 'wearing a bikini and lying on a bed with her arms stretched out'>, <describe the place, e.g. 'in a messy bedroom'>
            
            MAKE SURE to extract where she is from the text, and include that background in the webcam photo prompt, AND ALSO describe what she's doing according to the text.
            
            <EXAMPLES>
            webcam photo of a young american girl wearing a hoodie and glasses under the covers  dark room, grainy, candid, gritty, blurry, low quality
            
            webcam photo of a young asian girl wearing a a suit and pencil skirt while holding a pen and bending over in front of the bathroom mirror, grainy, candid, gritty, blurry, low quality
            
            a webcam photo of an asian woman wearing a thong and tank top posing seductively in a dorm room, holding up her hands in surprise, dark room, grainy, candid, gritty, blurry, low quality
            
            ONLY generate the prompt itself, avoid narrating or commenting, just write the short descriptive prompt.
            
            ALWAYS indicate what she's wearing in the photo, top and bottom, and where she is based on context.
            
            ALWAYS prioritize the latter part of the context to describe her body position and what she's doing.  use the earlier context mostly for deducing the setting."""

        prompt = "{image_generation_prompt}\n" + context
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates image prompts."},
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
                    image_prompt = response_json['choices'][0]['message']['content']
                    logger.info(f"Generated selfie prompt from OpenRouter: {image_prompt}")
                    print(f"\nGenerated image prompt:\n{image_prompt}")
                    return image_prompt
                else:
                    logger.error(f"Failed to get prompt from OpenRouter. Response: {response_json}")
                    return None

    async def generate_image(self, prompt):
        reactor_args = [
            None,  # Placeholder for img_base64
            True,  # Enable ReActor
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

        payload = {
            "sd_model_checkpoint": "iniverseMixXLSFWNSFW_guofenV15.safetensors",
            "prompt": prompt,
            "steps": 30,
            "sampler_name": "DPM++ 2M Karras",
            "width": 896,
            "height": 1152,
            "seed": -1,
            "guidance_scale": 7,
            "alwayson_scripts": {"reactor": {"args": reactor_args}}
        }

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

    # --- NEW FUNCTION START ---
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

            # Simple prompt asking the LLM to describe the character's current action
            system_prompt_for_action = """Analyze the last few messages of the conversation provided below. Based ONLY on the conversation context, describe the character's most likely current physical action and location in a very short phrase suitable for an image-to-video generation model.

Focus on a single, simple action. Examples: 'dancing in her room', 'sitting on the couch', 'walking outside', 'talking on the phone'.

Conversation Context:
{context}

Output ONLY the short action phrase."""

            prompt_content = system_prompt_for_action.format(context=combined_context)

        else:
            # Default prompt if no conversation history
            # Default prompt if no conversation history
            # Use a simple default action if no context
            prompt_content = "standing still"
            system_prompt_for_action = "Output the phrase 'standing still'." # Ensure LLM just outputs this

        # Use the APIManager's media LLM generation method
        try:
            action_prompt = await self.api_manager.generate_media_llm_response(
                system_prompt=system_prompt_for_action,
                user_prompt=prompt_content, # Pass the context-based prompt here
                max_tokens=30,
                temperature=0.3
            )

            if action_prompt:
                # Basic validation/cleanup
                action_prompt = re.sub(r'[^\w\s]', '', action_prompt) # Remove punctuation
                action_prompt = action_prompt.lower()
                # Prepend character description (optional, but might help WAN)
                # ethnicity = "asian woman" # Simplified, or extract like other prompts
                # final_prompt = f"{ethnicity} {action_prompt}"
                final_prompt = f"A woman is {action_prompt}" # Simple format based on WAN example
                logger.info(f"\nGenerated WAN video prompt: {final_prompt}")
                return final_prompt
            else:
                logger.error(f"Error generating WAN prompt: Media LLM returned None")
                return "A woman is talking" # Fallback prompt
        except Exception as e:
            logger.error(f"Exception generating WAN prompt: {e}", exc_info=True)
            return "A woman is talking" # Fallback prompt
    # --- NEW FUNCTION END ---

    # This is the original generate_video_prompt function
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
            
            print(f"\nGenerating video prompt using {len(bot_messages)} bot messages:")
            for i, msg in enumerate(bot_messages, 1):
                print(f"\nMessage {i}:\n{msg[:200]}...")  # Print first 200 chars of each message
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
                    print(f"\nGenerated video prompt:\n{video_prompt}")
                    return video_prompt
                else:
                    return None

    async def send_image(self, ctx, image_data):
        image_path = await self.save_image(image_data)
        with open(image_path, "rb") as f:
            await ctx.send(file=discord.File(f, os.path.basename(image_path)))
        return image_path
