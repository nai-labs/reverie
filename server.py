import os
import re
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
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
from tts_manager import TTSManager
from config import (
    DISCORD_BOT_TOKEN, # We might not need this, but config imports it
    COMMAND_PREFIX,
    characters
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
    tts_url: Optional[str] = None
    read_narration: Optional[bool] = None
    pov_mode: Optional[bool] = None

# --- Endpoints ---

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Web Dreams...")
    # Initialize managers
    # We need to initialize them with a session ID. 
    # For now, let's create a default session or load the last one.
    state.replicate_manager = ReplicateManager()
    state.api_manager = APIManager()
    # TTSManager needs character info, so we defer it
    state.tts_manager = None
    
    # We defer conversation_manager init until we know the user/character
    logger.info("Managers initialized.")

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
async def generate_image():
    if not state.image_manager:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # 1. Generate Prompt
    conversation = state.conversation_manager.get_conversation()
    
    # Get POV mode setting
    char_settings = characters.get(state.character_name, {})
    pov_mode = char_settings.get("pov_mode", False)
    
    prompt = await state.image_manager.generate_selfie_prompt(conversation, pov_mode=pov_mode)
    
    if not prompt:
        raise HTTPException(status_code=500, detail="Failed to generate image prompt")
        
    # 2. Generate Image
    image_data = await state.image_manager.generate_image(prompt)
    
    if not image_data:
        raise HTTPException(status_code=500, detail="Failed to generate image")
        
    # 3. Save Image
    image_path = await state.image_manager.save_image(image_data)
    
    # Update conversation manager with last selfie path (needed for video)
    state.conversation_manager.set_last_selfie_path(image_path)
    
    # Return relative path for frontend
    # image_path is absolute or relative to cwd. We need to make it relative to 'output' mount.
    # The save_image method saves to subfolder_path which is inside 'output/session_id'
    # We can just return the filename and construct the url, or return the full relative path.
    
    relative_path = os.path.relpath(image_path, start=os.getcwd())
    # Ensure forward slashes for URL
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
        "voice_settings": char_data.get("voice_settings", {}),
        "read_narration": char_data.get("read_narration", False),
        "pov_mode": char_data.get("pov_mode", False)
    }

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
