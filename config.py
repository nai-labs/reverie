import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Discord bot configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
COMMAND_PREFIX = '!'

# Logging configuration
LOG_LEVEL = logging.WARNING  # Only show warnings and errors for cleaner output
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
    "x-ai/grok-4.1-fast": "grok4.1",
    "deepseek/deepseek-chat-v3-0324": "deep",
    "deepseek/deepseek-r1-0528-qwen3-8b": "R1qwen3",
    "deepseek/deepseek-r1-0528": "R1deep",
    "deepseek/deepseek-v3.2": "deep.2",
    "x-ai/grok-4.1-fast:free": "grok4free",
    "mistralai/mistral-large-2512": "mistral",
    "anthropic/claude-sonnet-4.5": "sonnet4.5",
    "z-ai/glm-4.7": "glm4.7",
    "google/gemini-3-flash-preview": "gemini3"
   
   
   
}
OPENROUTER_MODEL = "x-ai/grok-4.1-fast"
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
LMSTUDIO_URL = os.getenv('LMSTUDIO_URL', 'http://localhost:1234/v1/chat/completions')
LMSTUDIO_HEADERS = {
    'Content-Type': 'application/json'
}
LMSTUDIO_MAX_TOKENS = 1024

# Default LLM model
DEFAULT_LLM = os.getenv('DEFAULT_LLM', 'openrouter')  # Can be "anthropic", "openrouter", or "lmstudio"

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
STABLE_DIFFUSION_URL = os.getenv('STABLE_DIFFUSION_URL', 'http://127.0.0.1:7860/sdapi/v1/txt2img')
INSIGHTFACE_MODEL_PATH = os.getenv("INSIGHTFACE_MODEL_PATH", './models/insightface/inswapper_128.onnx')

# Replicate API configuration
REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')

# Wavespeed API configuration
WAVESPEED_API_KEY = os.getenv('WAVESPEED_API_KEY')
WAVESPEED_API_URL = 'https://api.wavespeed.ai/api/v3'

# Hedra API configuration
HEDRA_API_KEY = os.getenv('HEDRA_API_KEY')
HEDRA_BASE_URL = 'https://mercury.dev.dream-ai.com/api'
HEDRA_HEADERS = {
    'X-API-KEY': HEDRA_API_KEY,
    'Content-Type': 'application/json'
}

# Zonos configuration
ZONOS_URL = os.getenv('ZONOS_URL', 'http://localhost:7860')

# Ngrok configuration
NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN')
USE_NGROK = os.getenv('USE_NGROK', 'false').lower() == 'true'

# API timeout settings
API_TIMEOUT = 300  # seconds
API_POLL_INTERVAL = 1  # seconds for polling prediction status

# Retry configuration for transient API failures
MAX_RETRIES = 3  # Number of retry attempts before giving up
RETRY_BASE_DELAY = 1.0  # Initial delay in seconds (doubles each retry: 1s, 2s, 4s)

# Image generation defaults (XL Mode)
IMAGE_WIDTH = 896
IMAGE_HEIGHT = 1152
IMAGE_STEPS = 30
IMAGE_GUIDANCE_SCALE = 4  # CFG Scale from UI
IMAGE_SAMPLER = "DPM++ 2M SDE"  # Sampler from UI
DEFAULT_SD_MODEL = "lustifySDXLNSFW_ggwpV7.safetensors"

# Z-Image mode settings (GGUF quantized for better VRAM efficiency)
LUMINA_SD_MODEL = "z-image-turbo-q4_k_m.gguf"
LUMINA_VAE = "z_ae.safetensors"
LUMINA_TEXT_ENCODER = "Qwen3-4B-Q4_K_M.gguf"  # GGUF text encoder
LUMINA_SAMPLER = "Euler"
LUMINA_SCHEDULER = "beta"
LUMINA_STEPS = 8
LUMINA_CFG_SCALE = 1
LUMINA_SHIFT = 4.0

# Video generation defaults
DEFAULT_VIDEO_DURATION = 10  # seconds for Kling videos

# Conversation limits
MAX_CONVERSATION_HISTORY = 100  # Maximum number of messages to keep in memory
MESSAGE_CHUNK_SIZE = 2000  # Character limit for Discord messages

# File management
MAX_FILE_AGE_DAYS = 30  # Days to keep generated files before cleanup

# Import characters after all configurations are set
from characters import characters
