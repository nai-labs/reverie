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
LOG_LEVEL = logging.DEBUG
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# OpenRouter API configuration
OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_HEADERS = {
    'Authorization': f'Bearer {OPENROUTER_KEY}',
    'X-Title': 'text-adventure-bot',
    'Content-Type': 'application/json'
}

# Only add HTTP-Referer if it's set in the environment
if os.getenv('OPENROUTER_HTTP_REFERER'):
    OPENROUTER_HEADERS['HTTP-Referer'] = os.getenv('OPENROUTER_HTTP_REFERER')

# Model configurations
CLAUDE_MODELS = {
    "claude-3-opus-20240229": "3opus",
    "claude-3-5-sonnet-20241022": "35sonnet",
    "claude-3-7-sonnet-20250219": "37sonnet"
}

OPENROUTER_MODELS = {
    "deepseek/deepseek-chat-v3-0324": "deep",
    "google/gemini-2.5-pro-exp-03-25:free": "gemprofree",
    "openai/gpt-4.5-preview": "4.5",
    "thedrummer/anubis-pro-105b-v1": "drummer",
    "latitudegames/wayfarer-large-70b-llama-3.3": "wayfarer",
    "x-ai/grok-2-1212": "grok",
    "cohere/command-a": "command-A",
    "google/gemini-2.0-flash-thinking-exp:free": "flashthink",
    "deepseek/deepseek-chat-v3-0324:free": "deepfree",
    "cohere/command-r-plus-04-2024": "command-R",
    "mistralai/mixtral-8x22b-instruct": "mixtral",
    "meta-llama/llama-3.1-405b-instruct": "405",
    "mistralai/mistral-large-2411": "mistral",
    "deepseek/deepseek-r1": "r1"
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

# Default LLM model
DEFAULT_LLM = os.getenv('DEFAULT_LLM', 'anthropic')  # Can be "anthropic" or "openrouter"

# OpenAI API configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_IMAGE_GENERATION_URL = 'https://api.openai.com/v1/images/generations'
OPENAI_IMAGE_EDIT_URL = 'https://api.openai.com/v1/images/edits'
OPENAI_HEADERS = {
    'Authorization': f'Bearer {OPENAI_API_KEY}',
    'Content-Type': 'application/json'
}
# Add Organization/Project headers if they exist in the environment
if os.getenv('OPENAI_ORGANIZATION'):
    OPENAI_HEADERS['OpenAI-Organization'] = os.getenv('OPENAI_ORGANIZATION')
if os.getenv('OPENAI_PROJECT'):
    OPENAI_HEADERS['OpenAI-Project'] = os.getenv('OPENAI_PROJECT')

# OpenAI Image Models (Focus on models supporting edits/multi-image)
OPENAI_IMAGE_MODELS = {
    "gpt-image-1": "gptimg1" # Supports multi-image edits
    # Add dall-e-3 or dall-e-2 if needed later, but they have limitations
}

# Default models
DEFAULT_CLAUDE_MODEL = "claude-3-opus-20240229"
DEFAULT_ADVENTURE_MODEL = "claude-3-opus-20240229"  # Using the most capable model for rich descriptions

# Stable Diffusion configuration
STABLE_DIFFUSION_URL = 'http://127.0.0.1:7860/sdapi/v1/txt2img'

# Stable Diffusion settings optimized for scene generation
STABLE_DIFFUSION_SCENE_SETTINGS = {
    "steps": 30,
    "sampler_name": "DPM++ 2M Karras",
    "width": 1024,  # Wider for better scene composition
    "height": 768,
    "guidance_scale": 7.5
}

# Import game masters after all configurations are set
from gamemasters import gamemasters
