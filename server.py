import os
import re
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
import zipfile
import io
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import json

# Import existing managers (we will refactor them slightly if needed)
from conversation_manager import ConversationManager
from database_manager import DatabaseManager
from api_manager import APIManager
from image_manager import ImageManager
from replicate_manager import ReplicateManager
from wavespeed_manager import WavespeedManager
from tts_manager import TTSManager
from config import (
    DISCORD_BOT_TOKEN, # We might not need this, but config imports it
    COMMAND_PREFIX,
    characters,
    USE_NGROK,
    NGROK_AUTH_TOKEN,
    SD_CHECKPOINTS_FOLDER
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Discord Dreams Web App")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# StaticFiles mount moved to end of file

# Serve output files (Images/Audio/Video)
if not os.path.exists("output"):
    os.makedirs("output")
app.mount("/output", StaticFiles(directory="output"), name="output")

# --- Global State ---
class AppState:
    def __init__(self):
        self.db = DatabaseManager()
        self.conversation_manager = None
        self.api_manager = None
        self.image_manager = None
        self.replicate_manager = None
        self.wavespeed_manager = None
        self.tts_manager = None
        self.user_id = "web_user" # Default user ID for web
        self.character_name = "Anika" # Default character

state = AppState()

# --- Models ---
class InitRequest(BaseModel):
    user: str
    character: str
    resume_session: Optional[str] = None  # Optional session folder to resume

class ChatRequest(BaseModel):
    message: str

class SettingsRequest(BaseModel):
    system_prompt: Optional[str] = None
    image_prompt: Optional[str] = None
    tts_url: Optional[str] = None
    read_narration: Optional[bool] = None
    pov_mode: Optional[bool] = None
    first_person_mode: Optional[bool] = None
    sd_mode: Optional[str] = None  # "xl" or "lumina"

# --- Endpoints ---

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Web Dreams...")
    # Initialize managers
    # We need to initialize them with a session ID. 
    # For now, let's create a default session or load the last one.
    state.replicate_manager = ReplicateManager()
    state.wavespeed_manager = WavespeedManager()
    
    # Load LLM settings from user_settings.json
    llm_settings = None
    try:
        if os.path.exists("user_settings.json"):
            with open("user_settings.json", "r") as f:
                llm_settings = json.load(f)
            logger.info(f"Loaded LLM settings: {llm_settings}")
    except Exception as e:
        logger.error(f"Failed to load user_settings.json: {e}")

    state.api_manager = APIManager(llm_settings)
    # TTSManager needs character info, so we defer it
    state.tts_manager = None
    
    # Load imported characters into the global characters dict
    try:
        if os.path.exists("imported_characters.json"):
            with open("imported_characters.json", "r", encoding="utf-8") as f:
                imported = json.load(f)
            characters.update(imported)
            logger.info(f"Loaded {len(imported)} imported characters: {list(imported.keys())}")
    except Exception as e:
        logger.error(f"Failed to load imported characters: {e}")
    
    # We defer conversation_manager init until we know the user/character
    logger.info("Managers initialized.")

    # Setup Ngrok if enabled
    if USE_NGROK and NGROK_AUTH_TOKEN:
        try:
            from pyngrok import ngrok
            ngrok.set_auth_token(NGROK_AUTH_TOKEN)
            public_url = ngrok.connect(8000).public_url
            logger.info(f"Public link created: {public_url}")
            # Write URL to a file for the launcher to read
            with open("latest_public_url.txt", "w") as f:
                f.write(public_url)
        except Exception as e:
            logger.error(f"Failed to start Ngrok: {e}")

@app.post("/api/init")
async def init_session(request: InitRequest):
    state.user_id = request.user
    state.character_name = request.character
    
    # Initialize ConversationManager
    state.conversation_manager = ConversationManager(state.character_name) 
    
    initial_message = None
    resumed = False
    
    # Check if resuming an existing session
    if request.resume_session:
        success = state.conversation_manager.resume_conversation(request.resume_session)
        if success:
            resumed = True
            logger.info(f"Resumed session: {request.resume_session}")
        else:
            logger.warning(f"Failed to resume session: {request.resume_session}, starting new session")
            state.conversation_manager.set_log_file("latest_session")
    else:
        # Create new session
        state.conversation_manager.set_log_file("latest_session")
    
    session_id = state.conversation_manager.session_id
    
    # Initialize ImageManager
    state.image_manager = ImageManager(state.conversation_manager, state.character_name, state.api_manager)
    
    # Initialize TTSManager
    state.tts_manager = TTSManager(state.character_name, state.conversation_manager)
    
    # Only generate initial message for NEW sessions (not resumed ones)
    if not resumed and state.character_name in characters:
        scenario = characters[state.character_name].get("scenario")
        if scenario:
            logger.info(f"Generating initial message for scenario: {scenario}")
            try:
                initial_message = await state.api_manager.generate_response(
                    message=scenario,
                    conversation=[],
                    system_prompt=characters[state.character_name].get("system_prompt", "")
                )
                
                if initial_message:
                    state.conversation_manager.add_assistant_response(initial_message)
            except Exception as e:
                logger.error(f"Failed to generate initial message: {e}")

    return {
        "status": "resumed" if resumed else "initialized", 
        "session_id": session_id, 
        "character": state.character_name,
        "initial_message": initial_message,
        "resumed": resumed
    }

@app.get("/api/session")
async def get_session():
    # Load settings to check for password
    requires_password = False
    try:
        if os.path.exists("user_settings.json"):
            with open("user_settings.json", "r") as f:
                settings = json.load(f)
                if settings.get("remote_password"):
                    requires_password = True
    except:
        pass

    return {
        "user": state.user_id,
        "character": state.character_name,
        "session_id": state.conversation_manager.session_id if state.conversation_manager else None,
        "requires_password": requires_password
    }

@app.get("/api/sessions")
async def get_sessions(character: Optional[str] = None):
    """Get all available sessions for resuming. Optionally filter by character."""
    sessions = ConversationManager.get_all_sessions()
    
    # Filter by character if specified
    if character:
        sessions = [s for s in sessions if s.get("character") == character]
    
    return {"sessions": sessions}

class AuthRequest(BaseModel):
    password: str

@app.post("/api/auth")
async def authenticate(request: AuthRequest):
    try:
        if os.path.exists("user_settings.json"):
            with open("user_settings.json", "r") as f:
                settings = json.load(f)
                stored_password = settings.get("remote_password")
                if stored_password and request.password == stored_password:
                    return {"success": True}
    except Exception as e:
        logger.error(f"Auth error: {e}")
    
    return {"success": False}

@app.get("/api/history")
async def get_history(request: Request): # Import Request from fastapi
    # Check password in header
    password = request.headers.get("X-Remote-Password")
    authorized = False
    
    # Localhost (host machine) is always authorized
    client_host = request.client.host if request.client else None
    if client_host in ("127.0.0.1", "localhost", "::1"):
        authorized = True
    
    if not authorized:
        try:
            if os.path.exists("user_settings.json"):
                with open("user_settings.json", "r") as f:
                    settings = json.load(f)
                    stored_password = settings.get("remote_password")
                    if not stored_password: # No password set
                        authorized = True
                    elif password == stored_password:
                        authorized = True
            else:
                authorized = True # No settings file
        except:
            pass
        
    if not authorized:
         raise HTTPException(status_code=401, detail="Unauthorized")

    if state.conversation_manager:
        return {"history": state.conversation_manager.get_conversation()}
    return {"history": []}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    user_msg = request.message
    
    # 1. Save user message
    state.conversation_manager.add_user_message(user_msg)
    
    # 2. Get LLM response
    history = state.conversation_manager.get_conversation()
    
    # Get system prompt (try to get from characters dict if manager doesn't expose it)
    system_prompt = characters[state.character_name]["system_prompt"]
    
    # Use APIManager to get response
    # We need to construct the messages list
    # Use APIManager to get response
    # APIManager expects (message, conversation, system_prompt)
    # history includes the latest user message, so we split it
    conversation_history = history[:-1] if history else []
    
    response_text = await state.api_manager.generate_response(
        message=user_msg,
        conversation=conversation_history,
        system_prompt=system_prompt
    )
    
    if not response_text:
        raise HTTPException(status_code=500, detail="Failed to generate response")
        
    # 4. Save bot message
    state.conversation_manager.add_assistant_response(response_text)
    
    return {
        "response": response_text,
        "history": history + [{"role": "assistant", "content": response_text}]
    }

class TTSRequest(BaseModel):
    text: str

@app.post("/api/generate/tts")
async def generate_tts(request: TTSRequest):
    if not state.tts_manager:
        raise HTTPException(status_code=400, detail="TTS not initialized")
        
    text = request.text
    tts_file = None
    
    try:
        # Use voice direction logic
        char_settings = characters.get(state.character_name, {})
        include_narration = char_settings.get("read_narration", False)
        
        voice_directed_text = await state.api_manager.generate_voice_direction(text, include_narration=include_narration)
        
        if voice_directed_text:
            tts_path = await state.tts_manager.generate_v3_tts(voice_directed_text)
            if tts_path:
                state.conversation_manager.set_last_audio_path(tts_path)
                # Return full relative path for URL
                relative_path = os.path.relpath(tts_path, start=os.getcwd())
                tts_file = "/" + relative_path.replace("\\", "/")
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")
        
    if not tts_file:
         raise HTTPException(status_code=500, detail="Failed to generate TTS")
         
    return {"tts_url": tts_file}

class ScriptTTSRequest(BaseModel):
    text: str

@app.post("/api/generate/script-tts")
async def generate_script_tts(request: ScriptTTSRequest):
    """Generate TTS from raw script text, bypassing voice direction."""
    if not state.tts_manager:
        raise HTTPException(status_code=400, detail="TTS not initialized")
    
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Script text is required")
    
    try:
        # Send raw text directly to ElevenLabs (no voice direction processing)
        tts_path = await state.tts_manager.generate_v3_tts(request.text.strip())
        
        if tts_path:
            # Set as last audio for S2V use
            state.conversation_manager.set_last_audio_path(tts_path)
            relative_path = os.path.relpath(tts_path, start=os.getcwd())
            tts_file = "/" + relative_path.replace("\\", "/")
            return {"tts_url": tts_file}
        else:
            raise HTTPException(status_code=500, detail="Failed to generate TTS audio")
            
    except Exception as e:
        logger.error(f"Script TTS generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Script TTS failed: {e}")

@app.get("/api/image-models")
async def get_image_models():
    """Scan SD checkpoints folder and return available models for dropdown."""
    import glob
    
    models = []
    
    # Scan for .safetensors and .gguf files in the checkpoints folder
    if os.path.exists(SD_CHECKPOINTS_FOLDER):
        # Support multiple model file extensions
        extensions = ["*.safetensors", "*.gguf"]
        for ext in extensions:
            pattern = os.path.join(SD_CHECKPOINTS_FOLDER, ext)
            for filepath in glob.glob(pattern):
                filename = os.path.basename(filepath)
                # Remove extension to get model name
                name_without_ext = filename.rsplit('.', 1)[0]
                
                # Determine mode from filename prefix
                # zImage*, z_image*, z-image* (any casing) → lumina mode
                name_lower = name_without_ext.lower()
                if name_lower.startswith('zimage') or name_lower.startswith('z_image') or name_lower.startswith('z-image'):
                    mode = 'lumina'
                else:
                    mode = 'xl'
                
                models.append({
                    "value": filename,  # Use full filename with extension as value
                    "label": name_without_ext,  # Display name without extension
                    "mode": mode,
                    "filename": filename
                })
        
        # Sort alphabetically, but put z-image models first
        models.sort(key=lambda x: (0 if x['mode'] == 'lumina' else 1, x['label'].lower()))
    else:
        logger.warning(f"SD checkpoints folder not found: {SD_CHECKPOINTS_FOLDER}")
    
    # Add Qwen cloud option at the end
    models.append({
        "value": "qwen-image-2512",
        "label": "☁️ Qwen 2512 (Cloud)",
        "mode": "cloud",
        "filename": None
    })
    
    return {"models": models}

@app.post("/api/generate/image")
async def generate_image(model: str = "z-image-turbo"):
    """Generate image with specified model."""
    if not state.image_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # Check if cloud model (Qwen)
    if model == "qwen-image-2512":
        return await generate_image_qwen()
    
    # Dynamic model detection based on filename prefix
    # zImage*, z_image*, z-image* (any casing) → lumina mode, all else → xl mode
    model_lower = model.lower()
    if model_lower.startswith("zimage") or model_lower.startswith("z_image") or model_lower.startswith("z-image"):
        sd_mode = "lumina"
    else:
        sd_mode = "xl"
    
    # Model value is already the full filename with extension from the dropdown
    sd_checkpoint = model
    
    logger.info(f"[Image Gen] Model: {model}, sd_mode: {sd_mode}, checkpoint: {sd_checkpoint}")
    
    # 1. Generate Prompt
    conversation = state.conversation_manager.get_conversation()
    
    # Get POV mode and First-Person mode settings
    char_settings = characters.get(state.character_name, {})
    pov_mode = char_settings.get("pov_mode", False)
    first_person_mode = char_settings.get("first_person_mode", False)
    
    prompt = await state.image_manager.generate_selfie_prompt(conversation, pov_mode=pov_mode, first_person_mode=first_person_mode)
    
    if not prompt:
        raise HTTPException(status_code=500, detail="Failed to generate image prompt")
        
    # 2. Generate Image
    image_data = await state.image_manager.generate_image(prompt, first_person_mode=first_person_mode, sd_mode=sd_mode, sd_checkpoint=sd_checkpoint)
    
    if not image_data:
        raise HTTPException(status_code=500, detail="Failed to generate image")
        
    # 3. Save Image
    image_path = await state.image_manager.save_image(image_data)
    
    # Update conversation manager with last selfie path (needed for video)
    state.conversation_manager.set_last_selfie_path(image_path)
    
    relative_path = os.path.relpath(image_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "image_url": f"/{relative_path}",
        "prompt": prompt
    }

async def generate_image_qwen():
    """Generate image using Qwen Image 2512 (cloud model via Replicate)."""
    if not state.replicate_manager:
        raise HTTPException(status_code=400, detail="Replicate manager not initialized")
    
    logger.info("[Qwen Image Gen] Starting cloud image generation...")
    
    # 1. Generate Prompt (same as local SD)
    conversation = state.conversation_manager.get_conversation()
    
    char_settings = characters.get(state.character_name, {})
    pov_mode = char_settings.get("pov_mode", False)
    first_person_mode = char_settings.get("first_person_mode", False)
    
    prompt = await state.image_manager.generate_selfie_prompt(conversation, pov_mode=pov_mode, first_person_mode=first_person_mode)
    
    if not prompt:
        raise HTTPException(status_code=500, detail="Failed to generate image prompt")
    
    logger.info(f"[Qwen Image Gen] Prompt: {prompt[:100]}...")
    
    # 2. Generate Image via Replicate
    image_url = await state.replicate_manager.generate_qwen_image(prompt, aspect_ratio="3:4")
    
    if not image_url:
        raise HTTPException(status_code=500, detail="Failed to generate image with Qwen")
    
    # 3. Download and save image
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            if resp.status == 200:
                image_data = await resp.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"qwen_image_{timestamp}.webp"
                image_path = os.path.join(state.conversation_manager.subfolder_path, image_filename)
                
                with open(image_path, "wb") as f:
                    f.write(image_data)
                    
                logger.info(f"[Qwen Image Gen] Saved to: {image_path}")
            else:
                raise HTTPException(status_code=500, detail="Failed to download generated image")
    
    # 4. Apply face swap (unless first_person_mode is enabled)
    final_path = image_path
    if not first_person_mode and state.image_manager:
        logger.info("[Qwen Image Gen] Applying face swap...")
        faceswap_path = await state.image_manager.apply_faceswap(image_path)
        if faceswap_path:
            final_path = faceswap_path
            logger.info(f"[Qwen Image Gen] Face swap applied: {final_path}")
        else:
            logger.warning("[Qwen Image Gen] Face swap failed, using original image")
    
    # Update conversation manager
    state.conversation_manager.set_last_selfie_path(final_path)
    
    relative_path = os.path.relpath(final_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "image_url": f"/{relative_path}",
        "prompt": prompt
    }

async def generate_image_direct_qwen():
    """Generate image using Qwen cloud model with prompt extracted from last bot message's delimited text."""
    if not state.replicate_manager:
        raise HTTPException(status_code=400, detail="Replicate manager not initialized")
    
    logger.info("[Qwen Direct Image] Starting cloud image generation...")
    
    # 1. Get the last bot message
    conversation = state.conversation_manager.get_conversation()
    bot_messages = [msg["content"] for msg in conversation if msg["role"] == "assistant"]
    
    if not bot_messages:
        raise HTTPException(status_code=400, detail="No bot messages found to extract prompt from")
    
    last_message = bot_messages[-1]
    
    # 2. Extract delimited text from the end of the message
    prompt = None
    
    pipe_match = re.search(r'[*_~]*\|([^|]+)\|[*_~]*\s*$', last_message)
    if pipe_match:
        prompt = pipe_match.group(1).strip()
    else:
        bracket_match = re.search(r'[*_~]*\[([^\]]+)\][*_~]*\s*$', last_message)
        if bracket_match:
            prompt = bracket_match.group(1).strip()
    
    if not prompt:
        raise HTTPException(status_code=400, detail="No delimited prompt found in the last message. Expected text between | | or [ ] at the end.")
    
    logger.info(f"[Qwen Direct Image] Extracted prompt: {prompt[:100]}...")
    
    # 3. Prepend character's image_prompt for consistent appearance
    char_settings = characters.get(state.character_name, {})
    first_person_mode = char_settings.get("first_person_mode", False)
    image_prompt = char_settings.get("image_prompt", "")
    if image_prompt:
        prompt = f"{image_prompt}, {prompt}"
        logger.info(f"[Qwen Direct Image] Combined prompt: {prompt[:100]}...")
    
    # 4. Generate Image via Replicate Qwen
    image_url = await state.replicate_manager.generate_qwen_image(prompt, aspect_ratio="3:4")
    
    if not image_url:
        raise HTTPException(status_code=500, detail="Failed to generate image with Qwen")
    
    # 5. Download and save image
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            if resp.status == 200:
                image_data = await resp.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"qwen_direct_{timestamp}.webp"
                image_path = os.path.join(state.conversation_manager.subfolder_path, image_filename)
                
                with open(image_path, "wb") as f:
                    f.write(image_data)
                    
                logger.info(f"[Qwen Direct Image] Saved to: {image_path}")
            else:
                raise HTTPException(status_code=500, detail="Failed to download generated image")
    
    # 6. Apply face swap (unless first_person_mode is enabled)
    final_path = image_path
    if not first_person_mode and state.image_manager:
        logger.info("[Qwen Direct Image] Applying face swap...")
        faceswap_path = await state.image_manager.apply_faceswap(image_path)
        if faceswap_path:
            final_path = faceswap_path
            logger.info(f"[Qwen Direct Image] Face swap applied: {final_path}")
        else:
            logger.warning("[Qwen Direct Image] Face swap failed, using original image")
    
    # Update conversation manager
    state.conversation_manager.set_last_selfie_path(final_path)
    
    relative_path = os.path.relpath(final_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "image_url": f"/{relative_path}",
        "prompt": prompt
    }

@app.post("/api/generate/image/direct")
async def generate_image_direct(model: str = "z-image-turbo"):
    """Generate image using prompt extracted directly from the last bot message's delimited text."""
    if not state.image_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # Check if cloud model (Qwen)
    if model == "qwen-image-2512":
        return await generate_image_direct_qwen()
    
    # Dynamic model detection based on filename prefix
    # zImage*, z_image*, z-image* (any casing) → lumina mode, all else → xl mode
    model_lower = model.lower()
    if model_lower.startswith("zimage") or model_lower.startswith("z_image") or model_lower.startswith("z-image"):
        sd_mode = "lumina"
    else:
        sd_mode = "xl"
    
    # Always pass the checkpoint filename (model value is already full filename with extension)
    sd_checkpoint = model
    
    logger.info(f"[Direct Image] Model: {model}, sd_mode: {sd_mode}, checkpoint: {sd_checkpoint}")
    
    # 1. Get the last bot message
    conversation = state.conversation_manager.get_conversation()
    bot_messages = [msg["content"] for msg in conversation if msg["role"] == "assistant"]
    
    if not bot_messages:
        raise HTTPException(status_code=400, detail="No bot messages found to extract prompt from")
    
    last_message = bot_messages[-1]
    
    # 2. Extract delimited text from the end of the message
    prompt = None
    
    pipe_match = re.search(r'[*_~]*\|([^|]+)\|[*_~]*\s*$', last_message)
    if pipe_match:
        prompt = pipe_match.group(1).strip()
    else:
        bracket_match = re.search(r'[*_~]*\[([^\]]+)\][*_~]*\s*$', last_message)
        if bracket_match:
            prompt = bracket_match.group(1).strip()
    
    if not prompt:
        raise HTTPException(status_code=400, detail="No delimited prompt found in the last message. Expected text between | | or [ ] at the end.")
    
    logger.info(f"[Direct Image] Extracted prompt: {prompt[:100]}...")
    
    # 3. Prepend character's image_prompt for consistent appearance/face swap
    char_settings = characters.get(state.character_name, {})
    first_person_mode = char_settings.get("first_person_mode", False)
    image_prompt = char_settings.get("image_prompt", "")
    if image_prompt:
        prompt = f"{image_prompt}, {prompt}"
        logger.info(f"[Direct Image] Combined prompt: {prompt[:100]}...")
    
    # 4. Generate Image
    image_data = await state.image_manager.generate_image(prompt, first_person_mode=first_person_mode, sd_mode=sd_mode, sd_checkpoint=sd_checkpoint)
    
    if not image_data:
        raise HTTPException(status_code=500, detail="Failed to generate image")
    
    # 5. Save Image
    image_path = await state.image_manager.save_image(image_data)
    state.conversation_manager.set_last_selfie_path(image_path)
    
    relative_path = os.path.relpath(image_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "image_url": f"/{relative_path}",
        "prompt": prompt
    }

@app.post("/api/generate/video")
async def generate_video():
    if not state.replicate_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
        
    # 1. Get Inputs (Last Image and Audio)
    image_path = state.conversation_manager.get_last_selfie_path()
    audio_path = state.conversation_manager.get_last_audio_file()
    
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=400, detail="No recent image found. Please generate an image first.")
        
    if not audio_path or not os.path.exists(audio_path):
        # For now, we require audio. Later we can make it optional or generate silent video.
        # Or we can generate a placeholder audio?
        # Let's require it for the "s2v" model as it stands for "sound to video" (actually it's image-to-video usually but wan-2.2-s2v implies sound?)
        # Actually wan-2.2-s2v is likely "Sound to Video" or "Image + Sound to Video".
        # If no audio, maybe we can use a silent file or just fail.
        raise HTTPException(status_code=400, detail="No recent audio found. Please chat to generate audio first.")

    # 2. Generate Prompt
    conversation = state.conversation_manager.get_conversation()
    prompt = await state.image_manager.generate_wan_video_prompt(conversation)
    
    # 3. Generate Video
    # This returns a URL (or list of URLs)
    output = await state.replicate_manager.generate_wan_s2v_video(image_path, audio_path, prompt)
    
    if not output:
        raise HTTPException(status_code=500, detail="Failed to generate video")
        
    video_url = output[0] if isinstance(output, list) else output
    
    # 4. Download Video
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(video_url) as resp:
            if resp.status == 200:
                video_data = await resp.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                video_filename = f"video_{timestamp}.mp4"
                video_path = os.path.join(state.conversation_manager.subfolder_path, video_filename)
                
                with open(video_path, "wb") as f:
                    f.write(video_data)
            else:
                raise HTTPException(status_code=500, detail="Failed to download generated video")
    
    # 5. Return relative path
    relative_path = os.path.relpath(video_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "video_url": f"/{relative_path}",
        "prompt": prompt
    }

@app.post("/api/generate/video/wavespeed")
async def generate_video_wavespeed(model: str = "infinitetalk"):
    """Generate video with specified model. Options: wan, infinitetalk, infinitetalk-fast, hunyuan-avatar"""
    
    # 1. Get Inputs (Last Image and Audio)
    image_path = state.conversation_manager.get_last_selfie_path()
    audio_path = state.conversation_manager.get_last_audio_file()
    
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=400, detail="No recent image found. Please generate an image first.")
        
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=400, detail="No recent audio found. Please generate audio first.")

    # 2. Generate Prompt
    conversation = state.conversation_manager.get_conversation()
    prompt = await state.image_manager.generate_wan_video_prompt(conversation)
    
    # 3. Generate Video based on model selection
    video_url = None
    
    if model == "wan":
        # Use Wavespeed WAN S2V (switched from Replicate)
        if not state.wavespeed_manager:
            raise HTTPException(status_code=400, detail="Wavespeed manager not initialized")
        video_url = await state.wavespeed_manager.generate_video(
            image_path, 
            audio_path,
            model="wan-s2v",
            prompt=prompt,
            resolution="480p"
        )
    else:
        # Use Wavespeed models
        if not state.wavespeed_manager:
            raise HTTPException(status_code=400, detail="Wavespeed manager not initialized")
        video_url = await state.wavespeed_manager.generate_video(
            image_path, 
            audio_path,
            model=model,
            prompt=prompt,
            resolution="480p"
        )
    
    if not video_url:
        raise HTTPException(status_code=500, detail=f"Failed to generate video with {model}")
    
    # 4. Download Video
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(video_url) as resp:
            if resp.status == 200:
                video_data = await resp.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                video_filename = f"{model}_video_{timestamp}.mp4"
                video_path = os.path.join(state.conversation_manager.subfolder_path, video_filename)
                
                with open(video_path, "wb") as f:
                    f.write(video_data)
            else:
                raise HTTPException(status_code=500, detail="Failed to download generated video")
    
    # 5. Return relative path
    relative_path = os.path.relpath(video_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "video_url": f"/{relative_path}",
        "prompt": prompt,
        "model": model
    }

class LoraVideoRequest(BaseModel):
    prompt: str
    lora_url: Optional[str] = None  # Now optional - can generate without LoRA
    lora_scale: float = 1.0
    lora_url_2: Optional[str] = None  # Optional second LoRA
    lora_scale_2: Optional[float] = None
    wan_model: str = "wan-2.1-lora"  # wan-2.2-fast for HuggingFace, wan-2.1-lora for CivitAI
    num_frames: int = 81
    fps: int = 16
    use_preview_image: bool = False  # If true, use the most recently generated image

@app.post("/api/generate/video/lora")
async def generate_video_lora(request: LoraVideoRequest):
    """Generate video using WAN with a custom LoRA."""
    
    if not state.replicate_manager:
        raise HTTPException(status_code=400, detail="Replicate manager not initialized")
    
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # 1. Get image - either the preview (last generated) or last selfie
    image_path = state.conversation_manager.get_last_selfie_path()
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=400, detail="No recent image found. Please generate an image first.")
    
    if request.use_preview_image:
        logger.info(f"[WAN Video] Using preview image: {image_path}")
    
    logger.info(f"[WAN Video] Model: {request.wan_model}")
    logger.info(f"[WAN Video] Prompt: {request.prompt[:50]}...")
    if request.lora_url:
        logger.info(f"[WAN Video] LoRA 1: {request.lora_url[:50]}... (scale: {request.lora_scale})")
    else:
        logger.info(f"[WAN Video] No LoRA - plain image-to-video")
    if request.lora_url_2:
        logger.info(f"[WAN Video] LoRA 2: {request.lora_url_2[:50]}... (scale: {request.lora_scale_2})")
    logger.info(f"[WAN Video] Frames: {request.num_frames}, FPS: {request.fps}")
    
    # 2. Generate Video
    output = await state.replicate_manager.generate_wan_lora_video(
        image_path=image_path,
        prompt=request.prompt,
        lora_url=request.lora_url,
        lora_scale=request.lora_scale,
        lora_url_2=request.lora_url_2,
        lora_scale_2=request.lora_scale_2,
        model=request.wan_model,
        num_frames=request.num_frames,
        fps=request.fps
    )
    
    if not output:
        raise HTTPException(status_code=500, detail="Failed to generate LoRA video")
    
    video_url = output[0] if isinstance(output, list) else output
    
    # 3. Download Video
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(video_url) as resp:
            if resp.status == 200:
                video_data = await resp.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                video_filename = f"lora_video_{timestamp}.mp4"
                video_path = os.path.join(state.conversation_manager.subfolder_path, video_filename)
                
                with open(video_path, "wb") as f:
                    f.write(video_data)
            else:
                raise HTTPException(status_code=500, detail="Failed to download generated video")
    
    # 4. Return relative path
    relative_path = os.path.relpath(video_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "video_url": f"/{relative_path}",
        "prompt": request.prompt
    }

@app.post("/api/generate/lipsync")
async def generate_lipsync(model: str = "veed"):
    """Lipsync last video with last audio. Models: veed (default), kling (relaxed), pixverse (express)."""
    
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # Get last video path
    video_path = state.conversation_manager.get_last_video_path()
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail="No video available for lipsync")
    
    # Get last audio path
    audio_path = state.conversation_manager.get_last_audio_path()
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=400, detail="No audio available for lipsync")
    
    logger.info(f"[Lipsync] Generating with model={model}, video={video_path}, audio={audio_path}")
    
    # Generate lipsync based on model selection
    video_url = None
    
    if model == "veed":
        # Wavespeed Veed Lipsync (default)
        if not state.wavespeed_manager:
            raise HTTPException(status_code=400, detail="Wavespeed manager not initialized")
        video_url = await state.wavespeed_manager.generate_lipsync(video_path, audio_path, model="veed")
        
    elif model == "pixverse":
        # Replicate Pixverse Lipsync (express - fast)
        if not state.replicate_manager:
            raise HTTPException(status_code=400, detail="Replicate manager not initialized")
        video_url = await state.replicate_manager.generate_pixverse_lipsync(video_path, audio_path)
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown lipsync model: {model}. Use: veed, pixverse")
    
    if not video_url:
        raise HTTPException(status_code=500, detail=f"Failed to generate lipsync with {model}")
    
    # Download the video
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(video_url) as resp:
            if resp.status == 200:
                video_data = await resp.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                video_filename = f"lipsync_{model}_{timestamp}.mp4"
                output_path = os.path.join(state.conversation_manager.subfolder_path, video_filename)
                
                with open(output_path, "wb") as f:
                    f.write(video_data)
                    
                # Set as last video for continuity
                state.conversation_manager.set_last_video_path(output_path)
            else:
                raise HTTPException(status_code=500, detail="Failed to download lipsynced video")
    
    relative_path = os.path.relpath(output_path, start=os.getcwd())
    relative_path = relative_path.replace("\\", "/")
    
    return {
        "video_url": f"/{relative_path}",
        "model": model
    }

class LoraItem(BaseModel):
    name: str
    url: str

class SyncLorasRequest(BaseModel):
    loras: list[LoraItem]

@app.post("/api/sync/loras")
async def sync_loras(request: SyncLorasRequest):
    """Download LoRA files to custom_loras folder for backup."""
    import aiohttp
    import urllib.parse
    
    # Create custom_loras folder if it doesn't exist
    loras_folder = os.path.join(os.getcwd(), "custom_loras")
    os.makedirs(loras_folder, exist_ok=True)
    
    downloaded = 0
    skipped = 0
    
    async with aiohttp.ClientSession() as session:
        for lora in request.loras:
            # Extract filename from URL
            parsed_url = urllib.parse.urlparse(lora.url)
            filename = os.path.basename(urllib.parse.unquote(parsed_url.path))
            
            # Use preset name if filename is unclear
            if not filename or not filename.endswith('.safetensors'):
                filename = f"{lora.name}.safetensors"
            
            filepath = os.path.join(loras_folder, filename)
            
            # Skip if already exists
            if os.path.exists(filepath):
                logger.info(f"[Sync] Skipping {filename} - already exists")
                skipped += 1
                continue
            
            try:
                logger.info(f"[Sync] Downloading {filename}...")
                async with session.get(lora.url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        logger.info(f"[Sync] Downloaded {filename} ({len(content) / 1024 / 1024:.1f} MB)")
                        downloaded += 1
                    else:
                        logger.error(f"[Sync] Failed to download {filename}: HTTP {resp.status}")
            except Exception as e:
                logger.error(f"[Sync] Error downloading {filename}: {e}")
    
    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "folder": loras_folder
    }

class SceneItem(BaseModel):
    url: str
    mediaType: str  # 'image' or 'video'

class CompileStoryRequest(BaseModel):
    scenes: List[SceneItem]  # List of scenes with url and mediaType

@app.post("/api/compile-story")
async def compile_story(request: CompileStoryRequest):
    """Compile multiple images/videos into a single story video using FFmpeg."""
    import subprocess
    import tempfile
    
    if not request.scenes or len(request.scenes) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 items to compile")
    
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    logger.info(f"[Compile Story] Compiling {len(request.scenes)} items...")
    
    # Convert scenes to absolute paths and track types
    scenes = []
    for scene in request.scenes:
        relative_path = scene.url.lstrip('/')
        absolute_path = os.path.join(os.getcwd(), relative_path)
        
        if not os.path.exists(absolute_path):
            raise HTTPException(status_code=400, detail=f"File not found: {scene.url}")
        
        scenes.append({
            'path': absolute_path,
            'mediaType': scene.mediaType
        })
        logger.info(f"[Compile Story] Added {scene.mediaType}: {absolute_path}")
    
    # Check if we have any images
    has_images = any(s['mediaType'] == 'image' for s in scenes)
    
    # Target resolution for all content
    TARGET_WIDTH = 1280
    TARGET_HEIGHT = 720
    SCALE_FILTER = f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=30"
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"story_{timestamp}.mp4"
        output_path = os.path.join(state.conversation_manager.subfolder_path, output_filename)
        
        # Always pre-process all scenes to normalize resolution
        temp_videos = []
        
        for i, scene in enumerate(scenes):
            temp_video = os.path.join(tempfile.gettempdir(), f"scene_{timestamp}_{i}.mp4")
            
            if scene['mediaType'] == 'image':
                # Convert image to 2s video at target resolution
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-i", scene['path'],
                    "-c:v", "libx264",
                    "-t", "2",  # 2 seconds
                    "-pix_fmt", "yuv420p",
                    "-vf", SCALE_FILTER,
                    temp_video
                ]
                subprocess.run(cmd, capture_output=True, timeout=30)
                temp_videos.append({'path': temp_video, 'temp': True})
            else:
                # Normalize video to target resolution
                cmd = [
                    "ffmpeg", "-y",
                    "-i", scene['path'],
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-vf", SCALE_FILTER,
                    "-c:a", "aac",
                    "-b:a", "128k",
                    temp_video
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode == 0:
                    temp_videos.append({'path': temp_video, 'temp': True})
                else:
                    # Fallback: use original if scaling fails
                    logger.warning(f"[Compile Story] Failed to scale video {i}, using original")
                    temp_videos.append({'path': scene['path'], 'temp': False})
        
        # Concatenate all normalized clips
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            concat_file = f.name
            for tv in temp_videos:
                escaped_path = tv['path'].replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",  # Stream copy since already encoded
            output_path
        ]
        
        logger.info(f"[Compile Story] Concatenating {len(temp_videos)} normalized clips to {TARGET_WIDTH}x{TARGET_HEIGHT}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # Clean up temp files
        os.unlink(concat_file)
        for tv in temp_videos:
            if tv['temp'] and os.path.exists(tv['path']):
                os.unlink(tv['path'])
        
        if result.returncode != 0:
            logger.error(f"[Compile Story] FFmpeg error: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"FFmpeg failed: {result.stderr[:200]}")
        
        logger.info(f"[Compile Story] Success! Output: {output_path}")
        
        relative_path = os.path.relpath(output_path, start=os.getcwd())
        relative_path = relative_path.replace("\\", "/")
        
        return {
            "video_url": f"/{relative_path}",
            "clips_count": len(scenes)
        }
        
    except subprocess.TimeoutExpired:
        logger.error("[Compile Story] FFmpeg timeout")
        raise HTTPException(status_code=500, detail="Video compilation timed out")
    except Exception as e:
        logger.error(f"[Compile Story] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ExtractFrameRequest(BaseModel):
    video_url: str

@app.post("/api/extract-frame")
async def extract_frame(request: ExtractFrameRequest):
    """Extract the last frame of a video and set it as the current image."""
    import subprocess
    
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # Convert URL to absolute path
    relative_path = request.video_url.lstrip('/')
    video_path = os.path.join(os.getcwd(), relative_path)
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail=f"Video not found: {request.video_url}")
    
    logger.info(f"[Extract Frame] Extracting last frame from: {video_path}")
    
    try:
        # Output path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"frame_{timestamp}.png"
        output_path = os.path.join(state.conversation_manager.subfolder_path, output_filename)
        
        # Use FFmpeg to extract last frame
        # First get video duration, then seek to near end
        cmd = [
            "ffmpeg", "-y",
            "-sseof", "-0.1",  # Seek to 0.1s before end
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0 or not os.path.exists(output_path):
            logger.error(f"[Extract Frame] FFmpeg error: {result.stderr}")
            raise HTTPException(status_code=500, detail="Failed to extract frame")
        
        logger.info(f"[Extract Frame] Frame extracted: {output_path}")
        
        # Apply face swap using ReActor (if image_manager is available)
        final_path = output_path
        if state.image_manager:
            logger.info("[Extract Frame] Applying face swap...")
            faceswap_path = await state.image_manager.apply_faceswap(output_path)
            if faceswap_path:
                final_path = faceswap_path
                logger.info(f"[Extract Frame] Face swap applied: {final_path}")
            else:
                logger.warning("[Extract Frame] Face swap failed, using original frame")
        
        # Set as last selfie path for next video generation
        state.conversation_manager.set_last_selfie_path(final_path)
        
        relative_path = os.path.relpath(final_path, start=os.getcwd())
        relative_path = relative_path.replace("\\", "/")
        
        return {
            "image_url": f"/{relative_path}"
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Frame extraction timed out")
    except Exception as e:
        logger.error(f"[Extract Frame] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/lora-presets")
async def get_lora_presets():
    """Serve LoRA presets from lora_presets.json file."""
    presets_path = os.path.join(os.getcwd(), "lora_presets.json")
    
    if not os.path.exists(presets_path):
        # Return empty if file doesn't exist
        return {"presets": {}}
    
    try:
        with open(presets_path, 'r', encoding='utf-8') as f:
            presets = json.load(f)
        return {"presets": presets}
    except Exception as e:
        logger.error(f"Error loading lora_presets.json: {e}")
        return {"presets": {}}

@app.get("/api/image-prompt-components")
async def get_image_prompt_components():
    """Serve image prompt components from image_prompts.json file."""
    prompts_path = os.path.join(os.getcwd(), "image_prompts.json")
    
    if not os.path.exists(prompts_path):
        return {"components": {}}
    
    try:
        with open(prompts_path, 'r', encoding='utf-8') as f:
            components = json.load(f)
        return {"components": components}
    except Exception as e:
        logger.error(f"Error loading image_prompts.json: {e}")
        return {"components": {}}

@app.get("/api/settings")
async def get_settings():
    if not state.character_name:
        raise HTTPException(status_code=400, detail="Session not initialized")
        
    char_data = characters.get(state.character_name, {})
    return {
        "system_prompt": char_data.get("system_prompt", ""),
        "image_prompt": char_data.get("image_prompt", ""),
        "tts_url": char_data.get("tts_url", ""),
        "voice_settings": char_data.get("voice_settings", {}),
        "read_narration": char_data.get("read_narration", False),
        "pov_mode": char_data.get("pov_mode", False),
        "first_person_mode": char_data.get("first_person_mode", False),
        "sd_mode": char_data.get("sd_mode", "lumina")
    }

@app.get("/api/export")
async def export_conversation():
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    try:
        history = state.conversation_manager.get_conversation()
        if not history:
            raise HTTPException(status_code=400, detail="No conversation to export")
            
        # Create ZIP in memory
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, "w", zipfile.ZIP_DEFLATED) as zip_file:
            conversation_text = ""
            
            # Build conversation text
            for i, msg in enumerate(history, 1):
                role = msg["role"].capitalize()
                content = msg["content"]
                conversation_text += f"[{i:03d}] [{role}]: {content}\n\n"
            
            # Add conversation text log
            zip_file.writestr("conversation_log.txt", conversation_text)
            
            # Get ALL media files from the session folder, sorted by creation time
            subfolder = state.conversation_manager.subfolder_path
            media_extensions = ('.png', '.jpg', '.jpeg', '.mp3', '.mp4', '.wav')
            all_files = []
            for f in os.listdir(subfolder):
                if f.endswith(media_extensions):
                    full_path = os.path.join(subfolder, f)
                    all_files.append((f, full_path, os.path.getctime(full_path)))
            
            # Sort by creation time (chronological order)
            all_files.sort(key=lambda x: x[2])
            
            # Add files to ZIP with sequential prefixes
            for i, (filename, full_path, _) in enumerate(all_files, 1):
                new_filename = f"{i:03d}_{filename}"
                zip_file.write(full_path, arcname=new_filename)
            
            # Generate standalone gallery.html
            gallery_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Reverie Export - {state.character_name}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; max-width: 900px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; color: #0ea5e9; }}
        .message {{ margin-bottom: 20px; padding: 15px; border-radius: 10px; background: #1e293b; border: 1px solid #334155; }}
        .user {{ border-left: 5px solid #0ea5e9; }}
        .assistant {{ border-left: 5px solid #6366f1; }}
        .role {{ font-weight: bold; margin-bottom: 5px; color: #94a3b8; }}
        .content {{ line-height: 1.5; white-space: pre-wrap; }}
        .media-section {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #334155; }}
        .media-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }}
        .media-item {{ background: #1e293b; padding: 10px; border-radius: 8px; }}
        .media-item img, .media-item video {{ width: 100%; border-radius: 5px; }}
        .media-item audio {{ width: 100%; }}
        .media-label {{ font-size: 12px; color: #94a3b8; margin-top: 5px; }}
    </style>
</head>
<body>
    <h1>Conversation with {state.character_name}</h1>
    <div id="chat">
"""
            # Add conversation messages
            for i, msg in enumerate(history, 1):
                role = msg["role"]
                content = msg["content"].replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                css_class = role
                display_role = "You" if role == "user" else state.character_name
                
                gallery_html += f"""
        <div class="message {css_class}">
            <div class="role">{display_role}</div>
            <div class="content">{content}</div>
        </div>
"""
            
            # Add media gallery section
            gallery_html += """
    </div>
    <div class="media-section">
        <h2>📸 Media Gallery</h2>
        <div class="media-grid">
"""
            for i, (filename, _, _) in enumerate(all_files, 1):
                zip_filename = f"{i:03d}_{filename}"
                if filename.endswith(('.png', '.jpg', '.jpeg')):
                    gallery_html += f'<div class="media-item"><img src="{zip_filename}"><div class="media-label">{zip_filename}</div></div>\n'
                elif filename.endswith('.mp3') or filename.endswith('.wav'):
                    gallery_html += f'<div class="media-item"><audio controls src="{zip_filename}"></audio><div class="media-label">{zip_filename}</div></div>\n'
                elif filename.endswith('.mp4'):
                    gallery_html += f'<div class="media-item"><video controls src="{zip_filename}"></video><div class="media-label">{zip_filename}</div></div>\n'
            
            gallery_html += """
        </div>
    </div>
</body>
</html>
"""
            zip_file.writestr("index.html", gallery_html)

        zip_io.seek(0)
        filename = f"reverie_export_{state.character_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        def iter_file():
            yield zip_io.getvalue()
            
        return StreamingResponse(
            iter_file(), 
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        import traceback
        with open("server_debug.log", "a") as f:
            f.write(f"\n[{datetime.now()}] Export Error: {e}\n{traceback.format_exc()}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings")
async def update_settings(settings: SettingsRequest):
    if not state.character_name:
        raise HTTPException(status_code=400, detail="Session not initialized")
        
    if state.character_name not in characters:
        raise HTTPException(status_code=404, detail="Character not found")
        
    # Update in memory
    if settings.system_prompt is not None:
        characters[state.character_name]["system_prompt"] = settings.system_prompt
        # Also update active manager if possible
        if state.conversation_manager:
            state.conversation_manager.system_prompt = settings.system_prompt
            
    if settings.image_prompt is not None:
        characters[state.character_name]["image_prompt"] = settings.image_prompt
        if state.image_manager:
            state.image_manager.image_prompt = settings.image_prompt
            
    if settings.tts_url is not None:
        characters[state.character_name]["tts_url"] = settings.tts_url
        
    if settings.read_narration is not None:
        characters[state.character_name]["read_narration"] = settings.read_narration
        
    if settings.pov_mode is not None:
        characters[state.character_name]["pov_mode"] = settings.pov_mode
        
    if settings.first_person_mode is not None:
        characters[state.character_name]["first_person_mode"] = settings.first_person_mode
    
    # Debug logging for sd_mode
    logger.info(f"[DEBUG] update_settings received sd_mode: {settings.sd_mode} (type: {type(settings.sd_mode).__name__ if settings.sd_mode else 'None'})")
    
    if settings.sd_mode is not None:
        characters[state.character_name]["sd_mode"] = settings.sd_mode
        logger.info(f"[DEBUG] Saved sd_mode='{settings.sd_mode}' to character '{state.character_name}'")
        
    # Save to file
    try:
        import json
        with open("characters.py", "w", encoding="utf-8") as f:
            f.write("characters = " + json.dumps(characters, indent=4, ensure_ascii=False).replace("false", "False").replace("true", "True").replace("null", "None"))
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings to file")
        
    return {"status": "updated"}

class EditImageRequest(BaseModel):
    image_url: str  # Relative URL like /conversations/.../image.png
    prompt: str     # Edit instruction

@app.post("/api/edit/image")
async def edit_image(request: EditImageRequest):
    """Edit an image using Qwen Image Edit 2511 via Replicate."""
    if not state.replicate_manager:
        raise HTTPException(status_code=400, detail="Replicate manager not initialized")
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    logger.info(f"[Image Edit] Editing image: {request.image_url} with prompt: {request.prompt[:50]}...")
    
    # Convert relative URL to absolute file path
    relative_path = request.image_url.lstrip('/')
    absolute_path = os.path.join(os.getcwd(), relative_path)
    
    if not os.path.exists(absolute_path):
        raise HTTPException(status_code=400, detail=f"Image not found: {request.image_url}")
    
    # For Replicate, we need a publicly accessible URL
    # Upload the image to Replicate first using base64 data URI
    import base64
    with open(absolute_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Determine mime type from extension
    ext = os.path.splitext(absolute_path)[1].lower()
    mime_types = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
    mime_type = mime_types.get(ext, 'image/png')
    
    # Create data URI for the image
    image_data_uri = f"data:{mime_type};base64,{image_data}"
    
    # Call the edit method
    edited_url = await state.replicate_manager.edit_image(image_data_uri, request.prompt)
    
    if not edited_url:
        raise HTTPException(status_code=500, detail="Failed to edit image")
    
    # Download the edited image
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(edited_url) as resp:
            if resp.status == 200:
                edited_data = await resp.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                edited_filename = f"edited_image_{timestamp}.webp"
                edited_path = os.path.join(state.conversation_manager.subfolder_path, edited_filename)
                
                with open(edited_path, "wb") as f:
                    f.write(edited_data)
                    
                logger.info(f"[Image Edit] Saved edited image to: {edited_path}")
            else:
                raise HTTPException(status_code=500, detail="Failed to download edited image")
    
    result_relative = os.path.relpath(edited_path, start=os.getcwd())
    result_relative = result_relative.replace("\\", "/")
    
    return {
        "image_url": f"/{result_relative}",
        "prompt": request.prompt
    }

class FaceswapRequest(BaseModel):
    image_url: str  # Relative URL like /conversations/.../image.png

@app.post("/api/faceswap")
async def faceswap_image(request: FaceswapRequest):
    """Apply face swap to any image using ReActor via local SD."""
    if not state.image_manager:
        raise HTTPException(status_code=400, detail="Image manager not initialized")
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    logger.info(f"[Faceswap] Processing image: {request.image_url}")
    
    # Convert relative URL to absolute file path
    relative_path = request.image_url.lstrip('/')
    absolute_path = os.path.join(os.getcwd(), relative_path)
    
    if not os.path.exists(absolute_path):
        raise HTTPException(status_code=400, detail=f"Image not found: {request.image_url}")
    
    # Apply face swap using existing image manager method
    faceswap_path = await state.image_manager.apply_faceswap(absolute_path)
    
    if not faceswap_path:
        raise HTTPException(status_code=500, detail="Face swap failed")
    
    logger.info(f"[Faceswap] Success! Saved to: {faceswap_path}")
    
    result_relative = os.path.relpath(faceswap_path, start=os.getcwd())
    result_relative = result_relative.replace("\\", "/")
    
    return {
        "image_url": f"/{result_relative}"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Serve static files (Frontend) manually to avoid shadowing API routes
@app.get("/")
async def read_index():
    return FileResponse('web/index.html')

@app.get("/{filename}")
async def read_root_file(filename: str):
    file_path = os.path.join("web", filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return {"detail": "Not Found"}, 404

if __name__ == "__main__":
    try:
        # Disable reload for stability
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
    except Exception as e:
        import traceback
        with open("server_debug.log", "w") as f:
            f.write(traceback.format_exc())
        print(e)
        input("Press Enter to close...")
