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

    async def generate_selfie_prompt(self, conversation, pov_mode=False, first_person_mode=False, spycam_mode=False):
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
            elif spycam_mode:
                # Spycam Mode - Fisheye surveillance camera style
                context += """
                The prompt should follow this fisheye surveillance camera format:

                A grainy, low-resolution security camera shot from a high angle, inside a fisheye lens distortion glass circle, highly distorted with a wide angle. [location description]. The subject is a [character description: body type, COLOR of top, COLOR of bottom, shoes/barefoot, position/action]. The edges warp dramatically toward the circular frame. [lighting]. Washed-out, desaturated colors with VHS-like grain. A digital timestamp overlay displays "[contextual date/time]" in blocky white font.

                AESTHETIC REQUIREMENTS:
                - ALWAYS include: "a shot from a high angle, inside a fisheye lens distortion glass circle, highly distorted with a wide angle"
                - Strong barrel distortion effect curving toward the edges
                - Overhead/ceiling-mounted camera perspective
                - Low quality, grainy surveillance footage look
                - Desaturated, muted color palette

                <EXAMPLES>
                A grainy, low-resolution security camera shot from a high angle, inside a fisheye lens distortion glass circle, highly distorted with a wide angle. A bedroom at night with dim lamp lighting. The subject is a young woman with dark hair wearing a white tank top and grey shorts, barefoot, sitting on the edge of the bed looking at her phone. The edges warp dramatically toward the circular frame. Infrared-tinted glow. Washed-out, desaturated colors with VHS-like grain. A digital timestamp overlay displays "2025-11-28 23:17" in blocky white font.

                A grainy, low-resolution security camera shot from a high angle, inside a fisheye lens distortion glass circle, highly distorted with a wide angle. A living room with soft ambient lighting from a TV. The subject is a woman in a light blue oversized t-shirt and black shorts, lying on the couch looking up lazily. The edges warp dramatically toward the circular frame. Cool blue TV glow mixed with warm lamp light. Washed-out, desaturated colors with VHS-like grain. A digital timestamp overlay displays "2025-11-29 02:34" in blocky white font.

                A grainy, low-resolution security camera shot from a high angle, inside a fisheye lens distortion glass circle, highly distorted with a wide angle. A hallway near the front door. The subject is a woman with her hair in a ponytail wearing a beige cardigan and grey yoga pants, white socks, walking toward the door looking back over her shoulder. The edges warp dramatically toward the circular frame. Harsh overhead fluorescent lighting. Washed-out, desaturated colors with VHS-like grain. A digital timestamp overlay displays "2025-11-28 18:42" in blocky white font.

                ONLY generate the prompt itself, avoid narrating or commenting.
                ALWAYS include the exact phrase: "a shot from a high angle, inside a fisheye lens distortion glass circle, highly distorted with a wide angle"
                ALWAYS include the COLOR of clothing items (top color, bottom color).
                ALWAYS indicate what she's wearing (top, bottom, footwear/barefoot) based on context.
                Generate a realistic timestamp based on the scene context (time of day, situation)."""
            else:
                # Default Selfie Mode
                context += """
                The prompt should follow this format (change <these parts> to suit the context of the conversation and how the character looks in a photo now):

                pov shot of <describe the character, e.g. 'a 20-year-old asian girl'> <describe what they're wearing and what they're doing', e.g. 'wearing a bikini and lying on a bed with her arms stretched out'>, <describe the place, e.g. 'in a messy bedroom'>, looking at viewer

                MAKE SURE to extract where she is from the text, and include that background in the webcam photo prompt, AND ALSO describe what she's doing according to the text.

                <EXAMPLES>
                pov shot of a young american girl wearing a hoodie and glasses under the covers, looking up at viewer, dark room, grainy, candid, gritty, blurry, low quality, flash photography

                pov shot of a young asian girl wearing a a suit and pencil skirt while holding a pen and bending over in front of the bathroom mirror, looking at viewer, grainy, candid, gritty, blurry, low quality, flash photography

                pov shot of an asian woman wearing a thong and tank top posing seductively in a dorm room, holding up her hands in surprise, looking at viewer, dark room, grainy, candid, gritty, blurry, low quality, flash photography

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

    async def generate_image(self, prompt, first_person_mode=False, sd_mode="lumina", sd_checkpoint=None):
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
        logger.info(f"[Image Gen] sd_mode='{sd_mode}', sd_checkpoint='{sd_checkpoint}'")
        if sd_mode == "lumina":
            # Lumina mode: uses Lumina VAE, sampler, scheduler, steps, CFG
            # But use the passed checkpoint (or fall back to default LUMINA_SD_MODEL)
            lumina_model = sd_checkpoint if sd_checkpoint else LUMINA_SD_MODEL
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
                "override_settings": {
                    "sd_model_checkpoint": lumina_model,
                    "sd_vae": LUMINA_VAE,
                    "forge_additional_modules": [
                        f"C:\\AI\\ForgeUI\\models\\VAE\\{LUMINA_VAE}",
                        f"C:\\AI\\ForgeUI\\models\\text_encoder\\{LUMINA_TEXT_ENCODER}"
                    ]
                }
            }
            logger.info(f"Using Lumina mode with model: {lumina_model}")
        else:
            # XL mode: use provided checkpoint or default
            xl_model = sd_checkpoint if sd_checkpoint else DEFAULT_SD_MODEL
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
                "override_settings": {
                    "sd_model_checkpoint": xl_model,
                    "sd_vae": "Automatic",
                    "forge_additional_modules": [],
                    "CLIP_stop_at_last_layers": 2
                }
            }
            logger.info(f"Using XL mode with model: {xl_model}")

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

    async def apply_faceswap(self, image_path: str, source_folder: str = None) -> str:
        """Apply ReActor face swap to an existing image using img2img with denoising_strength=0.
        
        Args:
            image_path: Path to the source image to face-swap
            source_folder: Optional custom source folder for faces (defaults to character's folder)
            
        Returns:
            Path to the face-swapped image, or None if failed
        """
        import base64
        
        logger.info(f"[FaceSwap] Applying face swap to: {image_path}")
        
        # Read and encode the source image
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        
        # ReActor args - same as generate_image but always enabled
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
            "elena.safetensors",  # Filename of the face model
            source_folder if source_folder else self.source_faces_folder,  # The path to the folder containing source faces images
            None,  # skip it for API
            True,  # Randomly select an image from the path
            True,  # Force Upscale even if no face found
            0.6,  # Face Detection Threshold
            2,  # Maximum number of faces to detect (0 is unlimited)
        ]
        
        # img2img payload using same settings as generate_image (Lumina mode)
        # but without sd_model_checkpoint override to use current loaded model
        payload = {
            "init_images": [image_base64],
            "denoising_strength": 0.1,
            "prompt": "",
            "steps": LUMINA_STEPS,
            "sampler_name": LUMINA_SAMPLER,
            "scheduler": LUMINA_SCHEDULER,
            "width": IMAGE_WIDTH,
            "height": IMAGE_HEIGHT,
            "seed": -1,
            "cfg_scale": LUMINA_CFG_SCALE,
            "alwayson_scripts": {"reactor": {"args": reactor_args}}
            # No override_settings - use current loaded model
        }
        
        img2img_url = STABLE_DIFFUSION_URL.replace("txt2img", "img2img")
        logger.info(f"[FaceSwap] Sending to img2img API: {img2img_url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(img2img_url, json=payload, headers={'Content-Type': 'application/json'}) as response:
                    if response.status == 200:
                        r = await response.json()
                        if 'images' in r and len(r['images']) > 0:
                            # Save the face-swapped image
                            result_data = r['images'][0]
                            result_image = Image.open(io.BytesIO(base64.b64decode(result_data.split(",", 1)[0])))
                            
                            # Save with new filename
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            output_filename = f"faceswap_{timestamp}.png"
                            output_path = os.path.join(self.conversation_manager.subfolder_path, output_filename)
                            result_image.save(output_path)
                            
                            logger.info(f"[FaceSwap] Success! Saved to: {output_path}")
                            return output_path
                        else:
                            logger.error("[FaceSwap] No images in response")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"[FaceSwap] API error {response.status}: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"[FaceSwap] Exception: {e}")
            return None


    async def generate_wan_video_prompt(self, conversation):
        """Generates a detailed action prompt for video based on the last assistant message."""
        
        # Get only the last assistant message
        last_assistant_message = None
        for msg in reversed(conversation):
            if msg["role"] == "assistant":
                last_assistant_message = msg["content"]
                break
        
        if not last_assistant_message:
            logger.info("No assistant message found, using default prompt")
            return "A woman is standing still looking at the camera."
        
        logger.info(f"\nGenerating video prompt from last message:\n{last_assistant_message[:300]}...")
        
        # New detailed system prompt
        system_prompt = """You are a video director creating a motion prompt for an AI video generator.

Given the character's last message (dialogue + narration), describe the character's physical performance AS THEY DELIVER this dialogue. 

Focus on:
1. **Body language and gestures** - What are they doing with their hands, body, posture?
2. **Facial expressions** - How does their face change as they speak?
3. **Movement** - Are they walking, sitting, leaning, turning?
4. **Emotional transitions** - Does their mood shift during the message?
5. **Eye contact** - Looking at camera, looking away, darting eyes?

Output format: A single detailed sentence describing the character's actions and expressions as they speak.

Examples:
- "She leans forward with an excited grin, gesturing enthusiastically with her hands while making direct eye contact, then playfully rolls her eyes."
- "She crosses her arms defensively, looks away with a pained expression, then softens and meets your gaze with vulnerability."
- "She stretches lazily on the bed, yawning, then props herself up on one elbow and gives a flirty wink."
- "She paces nervously, running her fingers through her hair, avoiding eye contact as she speaks hesitantly."

Do NOT include the dialogue itself. Only describe the physical performance."""

        user_prompt = f"""Character's last message:

{last_assistant_message}

Describe their physical performance as they deliver this."""

        # Use the APIManager's media LLM generation method
        try:
            action_prompt = await self.api_manager.generate_media_llm_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=150,
                temperature=0.7
            )

            if action_prompt:
                final_prompt = action_prompt.strip()
                logger.info(f"\nGenerated video prompt: {final_prompt}")
                return final_prompt
            else:
                logger.error("Error generating video prompt: Media LLM returned None")
                return "A woman is talking expressively"
        except Exception as e:
            logger.error(f"Exception generating video prompt: {e}", exc_info=True)
            return "A woman is talking expressively"

    async def generate_ltx_video_prompt(self, conversation, style_override: str = None):
        """Generates a detailed scene prompt for LTX-2 video generation with audio.
        
        The LLM will analyze the context and automatically choose the best video style:
        - Cinematic (dramatic, film-like shots)
        - Security cam / CCTV (surveillance footage aesthetic)
        - Handheld / Phone video (shaky, candid, intimate)
        - Webcam / Video call (static, front-facing)
        - Found footage (documentary, leaked video feel)
        
        The prompt includes actual dialogue in quotes for LTX-2 to generate speech.
        
        Args:
            conversation: The conversation history
            style_override: Optional style to force (cinematic, security, handheld, webcam, found_footage)
        """
        
        # Get only the last assistant message
        last_assistant_message = None
        for msg in reversed(conversation):
            if msg["role"] == "assistant":
                last_assistant_message = msg["content"]
                break
        
        if not last_assistant_message:
            logger.info("[LTX Prompt] No assistant message found, using default prompt")
            return "A woman looks at the camera and says 'Hello there.' Warm lighting, casual atmosphere."
        
        logger.info(f"\n[LTX Prompt] Generating from last message:\n{last_assistant_message[:300]}...")
        
        # Build the style guidance
        style_guidance = ""
        if style_override:
            style_map = {
                "cinematic": "Use CINEMATIC style: professional film quality, dramatic angles, smooth camera movement, Hollywood-style lighting.",
                "security": "Use SECURITY CAMERA style: grainy footage, fixed high-angle camera, timestamp overlay, surveillance aesthetic, muted colors.",
                "handheld": "Use HANDHELD/PHONE VIDEO style: slightly shaky camera, candid feel, intimate framing, natural lighting, like a personal video recording.",
                "webcam": "Use WEBCAM style: static front-facing camera, slightly lower quality, casual video call aesthetic.",
                "found_footage": "Use FOUND FOOTAGE style: documentary feel, realistic, as if this was leaked or discovered footage."
            }
            style_guidance = style_map.get(style_override, "")
        
        system_prompt = """You are a video director creating prompts for LTX-2, an AI that generates synchronized video AND audio together.

Your job is to describe WHAT SHE IS DOING - focus entirely on the person's physical performance, body language, movements, expressions, and vocalizations. Reference her in passing ("She...") and focus on:

1. **Posture & Position** - How she's sitting/standing/lying, body orientation
2. **Physical Actions** - What her body is doing, gestures, hand movements
3. **Breathing & Tension** - Uneven breath, tightening muscles, relaxing, trembling
4. **Facial Expressions** - Eyes widening, biting lip, surprised look, intensity, vulnerability
5. **Involuntary Reactions** - any physical involuntary reactions, including but NOT limited to breaths, Gasps, shivers, tremors, jerks, twitches, startled movements
6. **Vocalizations** - Speaking, whispering, moaning, gasping, sighing (include actual dialogue in quotes)
7. **Emotional State** - Caught off-guard, overwhelmed, struggling to maintain composure

FORMAT: Write as a flowing description of her physical performance. Start with her position, then describe her movements, reactions, and emotional state as the scene unfolds.

EXAMPLES:

- She is seated upright in the saddle, gripping the reins as the horse moves at a steady trot. Her breathing becomes uneven and her posture tightens; her eyes widen with a startled expression as she shifts her weight. Small tremors move through her shoulders and arms, and her hands momentarily lose precision on the reins. Her hips tense and subtly jerk with the rhythm, and she gasps, looking down as if surprised by her own reaction. Her whole frame shakes with short, involuntary motions, her expression caught somewhere between surprise and intensity.

- She lies on her stomach on the bed, propped on her elbows, speaking directly to camera. "So I have this crazy idea..." She bites her lower lip, her eyes flickering with mischief. Her shoulders roll slightly as she shifts her weight, and she lets out a soft, breathy laugh.

- She sits at her desk, leaning toward the camera with furrowed brows. Her fingers tap nervously on the table as she whispers: "Don't tell anyone, but..." She glances over her shoulder, then back, her expression a mix of conspiracy and excitement. A small shiver runs through her.

- She walks slowly, her steps deliberate, arms wrapped around herself. Her breath comes in short, visible puffs. She pauses, closes her eyes tight, and her whole body shudders. "I'm fine," she says, voice cracking, but tears are already welling up in her eyes.

IMPORTANT:
- Include actual dialogue in quotes for LTX-2 to generate speech
- Capture emotional intensity through physical description
- Keep it under 100 words but make it visceral and vivid""" + (f"\n\n{style_guidance}" if style_guidance else "")

        user_prompt = f"""Character's last message:

{last_assistant_message}

Create a detailed LTX-2 video prompt including the spoken dialogue."""

        # Use the APIManager's media LLM generation method
        try:
            scene_prompt = await self.api_manager.generate_media_llm_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=250,
                temperature=0.8  # Slightly higher for creative variety in style selection
            )

            if scene_prompt:
                final_prompt = scene_prompt.strip()
                logger.info(f"\n[LTX Prompt] Generated: {final_prompt}")
                return final_prompt
            else:
                logger.error("[LTX Prompt] Media LLM returned None")
                return "A woman looks at the camera and speaks warmly. Soft indoor lighting, casual atmosphere."
        except Exception as e:
            logger.error(f"[LTX Prompt] Exception: {e}", exc_info=True)
            return "A woman looks at the camera and speaks warmly. Soft indoor lighting, casual atmosphere."
