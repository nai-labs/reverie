# config.py

import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Discord bot configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_USER_ID = int(os.getenv('DISCORD_USER_ID', 0))
COMMAND_PREFIX = '!'

# Logging configuration
LOG_LEVEL = logging.DEBUG
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Memory configuration
MEMORY_ENABLED = False
MEMORY_FILE_PATH = 'bot_memory.json'

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
    "claude-3-5-sonnet-20240620": "35sonnet"
}

OPENROUTER_MODELS = {
    "x-ai/grok-2": "grok",
    "inflection/inflection-3-pi": "pi",
    "openai/gpt-4o": "4o",
    "openai/chatgpt-4o-latest": "4o-latest",
    "openai/gpt-4o-mini": "mini", 
    "alpindale/magnum-72b": "magnum",
    "aetherwiing/mn-starcannon-12b": "nemo",
    "alpindale/goliath-120b": "goliath",
    "nvidia/llama-3.1-nemotron-70b-instruct": "nemotron",
    "01-ai/yi-large": "yi",
    "google/gemini-pro-1.5": "gemini",
    "google/gemini-pro-1.5-exp": "gemini_exp",
    "meta-llama/llama-3.1-70b-instruct": "llama70b",
    "cognitivecomputations/dolphin-llama-3-70b":"dolphin",
    "openrouter/flavor-of-the-week": "fow",
    "sao10k/l3-stheno-8b": "stheno",
    "lynn/soliloquy-v3": "sol",
    "sao10k/l3.1-euryale-70b": "eur",
    "lizpreciatior/lzlv-70b-fp16-hf": "lzlv",
    "nousresearch/nous-capybara-34b": "nouscap",
    "xwin-lm/xwin-lm-70b": "xwin",
    "cohere/command-r-plus-04-2024": "command",
    "cohere/command-r-plus-08-2024": "commanturbo",
    "mistralai/mixtral-8x22b-instruct": "mistral-8x22",
    "microsoft/wizardlm-2-8x22b": "wizard",
    "meta-llama/llama-3.1-405b-instruct": "405",
    "nothingiisreal/mn-celeste-12b": "celeste",
    "ai21/jamba-1-5-large": "jamba",
    "mistralai/mistral-large": "mistral-l2",
    "qwen/qwen-2.5-72b-instruct": "qwen"
}
OPENROUTER_MODEL = list(OPENROUTER_MODELS.keys())[0]
OPENROUTER_TEMPERATURE = 0.7
OPENROUTER_MAX_TOKENS = 768

# Anthropic API configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_HEADERS = {
    'X-API-Key': ANTHROPIC_API_KEY,
    'Content-Type': 'application/json',
    'anthropic-version': '2023-06-01'
}
ANTHROPIC_MODEL = 'claude-3-opus-20240229'
ANTHROPIC_MAX_TOKENS = 1024

# LMStudio API configuration
LMSTUDIO_URL = 'http://localhost:1234/v1/chat/completions'
LMSTUDIO_HEADERS = {
    'Content-Type': 'application/json'
}
LMSTUDIO_MAX_TOKENS = 1024

# Default LLM model
DEFAULT_LLM = os.getenv('DEFAULT_LLM', 'anthropic')  # Can be "anthropic", "openrouter", or "lmstudio"

# Set the default Claude model
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20240620"

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

# Replicate API configuration
REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')

# Import characters after all configurations are set
from characters import characters
