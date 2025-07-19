# config.py
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Discord bot configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
COMMAND_PREFIX = '!'

# Logging configuration
LOG_LEVEL = logging.INFO # Changed from DEBUG to INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# OpenRouter API configuration
OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_HEADERS = {
    'Authorization': f'Bearer {OPENROUTER_KEY}',
    'X-Title': 'discord-dreams',
    'Content-Type': 'application/json'
}

# Only add HTTP-Referer if it's set in the environment
if os.getenv('OPENROUTER_HTTP_REFERER'):
    OPENROUTER_HEADERS['HTTP-Referer'] = os.getenv('OPENROUTER_HTTP_REFERER')

CLAUDE_MODELS = {
    "claude-3-opus-20240229": "3opus",
    "claude-opus-4-20250514": "4opus",
    "claude-3-5-sonnet-20241022": "35sonnet",
    "claude-3-7-sonnet-20250219": "37sonnet",
    "claude-sonnet-4-20250514": "4sonnet"
}

OPENROUTER_MODELS = {
    "thedrummer/valkyrie-49b-v1": "drummer",
    "anthropic/claude-sonnet-4": "sonnet4",
    "deepseek/deepseek-chat-v3-0324": "deep",
    "deepseek/deepseek-chat-v3-0324:free": "deepfree",
    "google/gemini-2.5-flash-preview": "FLASH2.5",
    "google/gemini-2.5-pro-preview": "gempro",
    "openai/gpt-4.1": "4.1",
    "x-ai/grok-3-beta": "grok",
    "x-ai/grok-4": "grok4",
    "cohere/command-r-plus-04-2024": "command-R+",
    "mistralai/mistral-medium-3": "mixtral-med",
    "meta-llama/llama-4-maverick:free": "maverick"
   
}
OPENROUTER_MODEL = "deepseek/deepseek-r1"  
OPENROUTER_MAX_TOKENS = 1024

# Anthropic API configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_HEADERS = {
    'X-API-Key': ANTHROPIC_API_KEY,
    'Content-Type': 'application/json',
    'anthropic-version': '2023-06-01'
}

ANTHROPIC_MODEL = 'claude-3-5-sonnet-20241022'
ANTHROPIC_MAX_TOKENS = 2048

# LMStudio API configuration
LMSTUDIO_URL = 'http://localhost:1234/v1/chat/completions'
LMSTUDIO_HEADERS = {
    'Content-Type': 'application/json'
}
LMSTUDIO_MAX_TOKENS = 1024

# Default LLM model
DEFAULT_LLM = os.getenv('DEFAULT_LLM', 'anthropic')  # Can be "anthropic", "openrouter", or "lmstudio"

# Set the default Claude model
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
# claude-3-5-sonnet-20241022
# claude-3-opus-20240229
# claude-3-5-sonnet-20240620

# ElevenLabs API configuration
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_TTS_URL = 'https://api.elevenlabs.io/v1/text-to-speech/CzTZ4lZiNBohY9dgHW4V'
ELEVENLABS_HEADERS = {
    'Content-Type': 'application/json',
    'xi-api-key': ELEVENLABS_API_KEY,
    'model_id': 'eleven_multilingual_v2',
}
ELEVENLABS_MODEL_ID = 'eleven_multilingual_v2'
ELEVENLABS_VOICE_SETTINGS = {
    'stability': 0.10,
    'similarity_boost': 1,
    'use_speaker_boost': True
}
ELEVENLABS_OUTPUT_FORMAT = 'mp3_44100_192'

# Stable Diffusion API configuration
STABLE_DIFFUSION_URL = 'http://127.0.0.1:7860/sdapi/v1/txt2img'
INSIGHTFACE_MODEL_PATH = os.getenv("INSIGHTFACE_MODEL_PATH", 'C:/AI/newforge/webui_forge_cu121_torch231/webui/models/insightface/inswapper_128.onnx')

# Replicate API configuration
REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')

# Hedra API configuration
HEDRA_API_KEY = os.getenv('HEDRA_API_KEY')
HEDRA_BASE_URL = 'https://mercury.dev.dream-ai.com/api'
HEDRA_HEADERS = {
    'X-API-KEY': HEDRA_API_KEY,
    'Content-Type': 'application/json'
}

# Zonos configuration
ZONOS_URL = os.getenv('ZONOS_URL', 'https://52a139f01540aa0a5c.gradio.live')

# Import characters after all configurations are set
from characters import characters
