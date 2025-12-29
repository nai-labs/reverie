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
    NGROK_AUTH_TOKEN
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
    
    # Create/Load session
    state.conversation_manager.set_log_file("latest_session") # Or use a specific name
    session_id = state.conversation_manager.session_id
    
    # Initialize ImageManager
    state.image_manager = ImageManager(state.conversation_manager, state.character_name, state.api_manager)
    
    # Initialize TTSManager
    state.tts_manager = TTSManager(state.character_name, state.conversation_manager)
    
    initial_message = None
    # Check for scenario and generate initial message
    if state.character_name in characters:
        scenario = characters[state.character_name].get("scenario")
        if scenario:
            logger.info(f"Generating initial message for scenario: {scenario}")
            try:
                # Use APIManager to generate response based on scenario
                # We pass the scenario as the message, but with empty history
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
        "status": "initialized", 
        "session_id": session_id, 
        "character": state.character_name,
        "initial_message": initial_message
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

@app.post("/api/generate/image")
async def generate_image(model: str = "z-image-turbo"):
    """Generate image with specified model. Options: z-image-turbo, xl-lustify, xl-epicrealism"""
    if not state.image_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # Map model to sd_mode and checkpoint
    from config import DEFAULT_SD_MODEL, EPICREALISM_SD_MODEL
    if model == "z-image-turbo":
        sd_mode = "lumina"
        sd_checkpoint = None  # Uses default lumina model
    elif model == "xl-lustify":
        sd_mode = "xl"
        sd_checkpoint = DEFAULT_SD_MODEL
    elif model == "xl-epicrealism":
        sd_mode = "xl"
        sd_checkpoint = EPICREALISM_SD_MODEL
    else:
        sd_mode = "lumina"
        sd_checkpoint = None
    
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

@app.post("/api/generate/image/direct")
async def generate_image_direct(model: str = "z-image-turbo"):
    """Generate image using prompt extracted directly from the last bot message's delimited text."""
    if not state.image_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # Map model to sd_mode and checkpoint
    from config import DEFAULT_SD_MODEL, EPICREALISM_SD_MODEL
    if model == "z-image-turbo":
        sd_mode = "lumina"
        sd_checkpoint = None
    elif model == "xl-lustify":
        sd_mode = "xl"
        sd_checkpoint = DEFAULT_SD_MODEL
    elif model == "xl-epicrealism":
        sd_mode = "xl"
        sd_checkpoint = EPICREALISM_SD_MODEL
    else:
        sd_mode = "lumina"
        sd_checkpoint = None
    
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
        # Use Replicate WAN S2V
        if not state.replicate_manager:
            raise HTTPException(status_code=400, detail="Replicate manager not initialized")
        output = await state.replicate_manager.generate_wan_s2v_video(image_path, audio_path, prompt)
        video_url = output[0] if isinstance(output, list) else output
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
    lora_url: str
    lora_scale: float = 1.0
    wan_model: str = "wan-2.1-lora"  # wan-2.2-fast for HuggingFace, wan-2.1-lora for CivitAI
    num_frames: int = 81
    fps: int = 16

@app.post("/api/generate/video/lora")
async def generate_video_lora(request: LoraVideoRequest):
    """Generate video using WAN with a custom LoRA."""
    
    if not state.replicate_manager:
        raise HTTPException(status_code=400, detail="Replicate manager not initialized")
    
    if not state.conversation_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # 1. Get last image
    image_path = state.conversation_manager.get_last_selfie_path()
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=400, detail="No recent image found. Please generate an image first.")
    
    logger.info(f"[LoRA Video] Model: {request.wan_model}")
    logger.info(f"[LoRA Video] Prompt: {request.prompt[:50]}...")
    logger.info(f"[LoRA Video] LoRA URL: {request.lora_url[:50]}...")
    logger.info(f"[LoRA Video] LoRA Scale: {request.lora_scale}, Frames: {request.num_frames}, FPS: {request.fps}")
    
    # 2. Generate Video
    output = await state.replicate_manager.generate_wan_lora_video(
        image_path=image_path,
        prompt=request.prompt,
        lora_url=request.lora_url,
        lora_scale=request.lora_scale,
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
