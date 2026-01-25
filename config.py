import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _load_user_settings(path: str = "user_settings.json") -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning(f"Failed to load {path}: {exc}")
        return {}


@dataclass(frozen=True)
class Settings:
    # Discord
    discord_bot_token: Optional[str] = None
    command_prefix: str = "!"

    # LLM defaults + model registries
    claude_models: Dict[str, str] = field(default_factory=dict)
    openrouter_models: Dict[str, str] = field(default_factory=dict)
    default_llm: str = "openrouter"
    default_claude_model: str = "claude-3-5-sonnet-20241022"
    default_openrouter_model: str = "x-ai/grok-4.1-fast"
    default_lmstudio_model: Optional[str] = None
    default_media_llm_provider: str = "openrouter"
    default_media_llm_model: str = "x-ai/grok-4.1-fast"

    # OpenRouter
    openrouter_key: Optional[str] = None
    openrouter_url: str = "https://openrouter.ai/api/v1/chat/completions"
    openrouter_http_referer: Optional[str] = None
    openrouter_headers: Dict[str, str] = field(default_factory=dict)
    openrouter_max_tokens: int = 1024

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_headers: Dict[str, str] = field(default_factory=dict)
    anthropic_max_tokens: int = 2048

    # LMStudio
    lmstudio_url: str = "http://localhost:1234/v1/chat/completions"
    lmstudio_headers: Dict[str, str] = field(default_factory=dict)
    lmstudio_max_tokens: int = 1024

    # ElevenLabs
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_tts_url: str = "https://api.elevenlabs.io/v1/text-to-speech/CzTZ4lZiNBohY9dgHW4V"
    elevenlabs_headers: Dict[str, str] = field(default_factory=dict)
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_voice_settings: Dict[str, float] = field(default_factory=lambda: {
        "stability": 0.10,
        "similarity_boost": 1,
        "use_speaker_boost": True,
    })
    elevenlabs_output_format: str = "mp3_44100_192"

    # Stable Diffusion / Image
    stable_diffusion_url: str = "http://127.0.0.1:7860/sdapi/v1/txt2img"
    insightface_model_path: str = "./models/insightface/inswapper_128.onnx"
    sd_checkpoints_folder: str = "C:/AI/ForgeUI/models/Stable-diffusion"

    image_width: int = 896
    image_height: int = 1152
    image_steps: int = 30
    image_guidance_scale: int = 4
    image_sampler: str = "DPM++ 2M SDE"
    default_sd_model: str = "lustifySDXLNSFW_ggwpV7.safetensors"
    epicrealism_sd_model: str = "epicrealismXL_vxviiCrystalclear.safetensors"
    sd_models: Dict[str, str] = field(default_factory=dict)

    # Z-Image / Lumina
    lumina_sd_model: str = "z-image-turbo-q4_k_m.gguf"
    lumina_vae: str = "z_ae.safetensors"
    lumina_text_encoder: str = "Qwen3-4B-Q4_K_M.gguf"
    lumina_sampler: str = "Euler"
    lumina_scheduler: str = "beta"
    lumina_steps: int = 8
    lumina_cfg_scale: int = 1
    lumina_shift: float = 4.0

    # Video
    default_video_duration: int = 10

    # API keys & URLs
    replicate_api_token: Optional[str] = None
    wavespeed_api_key: Optional[str] = None
    wavespeed_api_url: str = "https://api.wavespeed.ai/api/v3"
    civitai_api_token: Optional[str] = None
    hedra_api_key: Optional[str] = None
    hedra_base_url: str = "https://mercury.dev.dream-ai.com/api"
    hedra_headers: Dict[str, str] = field(default_factory=dict)
    zonos_url: str = "http://localhost:7860"

    # Ngrok / remote
    ngrok_auth_token: Optional[str] = None
    use_ngrok: bool = False
    remote_password: str = ""

    # Retry + timeout
    api_timeout: int = 300
    api_poll_interval: int = 1
    max_retries: int = 3
    retry_base_delay: float = 1.0

    # Conversation limits
    max_conversation_history: int = 100
    message_chunk_size: int = 2000

    # File management
    max_file_age_days: int = 30


def _normalize_sd_url(raw_url: str) -> str:
    if raw_url and not raw_url.endswith('/sdapi/v1/txt2img'):
        return f"{raw_url.rstrip('/')}/sdapi/v1/txt2img"
    return raw_url


def build_settings(user_settings: Optional[Dict] = None) -> Settings:
    user_settings = user_settings or _load_user_settings()

    claude_models = {
        "claude-3-opus-20240229": "3opus",
        "claude-opus-4-20250514": "4opus",
        "claude-3-5-sonnet-20241022": "35sonnet",
        "claude-3-7-sonnet-20250219": "37sonnet",
        "claude-sonnet-4-20250514": "4sonnet",
    }
    openrouter_models = {
        "xiaomi/mimo-v2-flash:free": "mimo",
        "deepseek/deepseek-v3.2": "deep",
        "x-ai/grok-4.1-fast": "grok4.1",
        "moonshotai/kimi-k2-0905": "kimi",
        "z-ai/glm-4.7": "glm4.7",
        "deepseek/deepseek-r1-0528": "R1deep",
        "mistralai/mistral-large-2512": "mistral",
        "google/gemini-3-flash-preview": "gemini3",
        "deepseek/deepseek-r1-0528-qwen3-8b": "R1qwen3",
        "anthropic/claude-sonnet-4.5": "sonnet4.5",
    }
    sd_models = {
        "Z-Image Turbo": "z-image-turbo-q4_k_m.gguf",
        "XL Lustify": "lustifySDXLNSFW_ggwpV7.safetensors",
        "XL EpicRealism": "epicrealismXL_vxviiCrystalclear.safetensors",
        "BigLove Insta": "bigLove_insta1.safetensors",
        "MOHAWK v20": "MOHAWK_v20.safetensors",
        "Colossus XL": "colossusProjectXLSFW_12cExperimental3.safetensors",
        "Juggernaut XL": "juggernautXL_v8Rundiffusion.safetensors",
        "Pikon Realism": "pikonRealism_v2.safetensors",
        "Realistic Stock": "realisticStockPhoto_v20.safetensors",
        "Unstable Illusion": "unstableIllusion_sdxxl.safetensors",
        "Unstable Illusion V2": "unstableIllusion_sdxxxlV2.safetensors",
    }

    openrouter_key = os.getenv("OPENROUTER_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
    replicate_api_token = os.getenv("REPLICATE_API_TOKEN")
    wavespeed_api_key = os.getenv("WAVESPEED_API_KEY")
    civitai_api_token = os.getenv("CIVITAI_API_TOKEN")
    hedra_api_key = os.getenv("HEDRA_API_KEY")

    openrouter_headers = {
        "Authorization": f"Bearer {openrouter_key}" if openrouter_key else "",
        "X-Title": "discord-dreams",
        "Content-Type": "application/json",
    }
    if os.getenv("OPENROUTER_HTTP_REFERER"):
        openrouter_headers["HTTP-Referer"] = os.getenv("OPENROUTER_HTTP_REFERER")

    anthropic_headers = {
        "X-API-Key": anthropic_api_key or "",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    elevenlabs_headers = {
        "Content-Type": "application/json",
        "xi-api-key": elevenlabs_api_key or "",
        "model_id": "eleven_multilingual_v2",
    }

    hedra_headers = {
        "X-API-KEY": hedra_api_key or "",
        "Content-Type": "application/json",
    }

    # Defaults that can be overridden by user_settings (UI wins)
    main_provider = (user_settings.get("main_provider") or os.getenv("DEFAULT_LLM") or "OpenRouter").lower()
    media_provider = user_settings.get("media_provider", "OpenRouter").lower()

    default_llm = main_provider
    default_claude_model = os.getenv("DEFAULT_CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    default_openrouter_model = os.getenv("DEFAULT_OPENROUTER_MODEL", "x-ai/grok-4.1-fast")
    default_lmstudio_model = None

    user_main_model = user_settings.get("main_model")
    if user_main_model and main_provider == "openrouter":
        default_openrouter_model = user_main_model.split(" (")[0]
    elif user_main_model and main_provider == "anthropic":
        default_claude_model = user_main_model.split(" (")[0]
    elif user_main_model and main_provider == "lmstudio":
        default_lmstudio_model = user_main_model.split(" (")[0]

    user_media_model = user_settings.get("media_model")
    default_media_provider = media_provider
    if user_media_model and media_provider == "openrouter":
        default_media_model = user_media_model.split(" (")[0]
    else:
        default_media_model = default_openrouter_model

    stable_diffusion_url = _normalize_sd_url(os.getenv("STABLE_DIFFUSION_URL", "http://127.0.0.1:7860/sdapi/v1/txt2img"))

    use_ngrok = user_settings.get("use_ngrok")
    if use_ngrok is None:
        use_ngrok = os.getenv("USE_NGROK", "false").lower() == "true"

    remote_password = user_settings.get("remote_password", "")

    ngrok_auth_token = user_settings.get("ngrok_auth_token") or os.getenv("NGROK_AUTH_TOKEN")

    settings = Settings(
        discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
        command_prefix="!",
        claude_models=claude_models,
        openrouter_models=openrouter_models,
        default_llm=default_llm,
        default_claude_model=default_claude_model,
        default_openrouter_model=default_openrouter_model,
        default_lmstudio_model=default_lmstudio_model,
        default_media_llm_provider=default_media_provider,
        default_media_llm_model=default_media_model,
        openrouter_key=openrouter_key,
        openrouter_url=os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"),
        openrouter_http_referer=os.getenv("OPENROUTER_HTTP_REFERER"),
        openrouter_headers=openrouter_headers,
        openrouter_max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "1024")),
        anthropic_api_key=anthropic_api_key,
        anthropic_url=os.getenv("ANTHROPIC_URL", "https://api.anthropic.com/v1/messages"),
        anthropic_headers=anthropic_headers,
        anthropic_max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "2048")),
        lmstudio_url=os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions"),
        lmstudio_headers={"Content-Type": "application/json"},
        lmstudio_max_tokens=int(os.getenv("LMSTUDIO_MAX_TOKENS", "1024")),
        elevenlabs_api_key=elevenlabs_api_key,
        elevenlabs_tts_url=os.getenv("ELEVENLABS_TTS_URL", "https://api.elevenlabs.io/v1/text-to-speech/CzTZ4lZiNBohY9dgHW4V"),
        elevenlabs_headers=elevenlabs_headers,
        elevenlabs_model_id="eleven_multilingual_v2",
        elevenlabs_voice_settings={
            "stability": float(os.getenv("ELEVENLABS_VOICE_STABILITY", "0.10")),
            "similarity_boost": float(os.getenv("ELEVENLABS_VOICE_SIMILARITY", "1")),
            "use_speaker_boost": os.getenv("ELEVENLABS_USE_SPEAKER_BOOST", "true").lower() == "true",
        },
        elevenlabs_output_format=os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_192"),
        stable_diffusion_url=stable_diffusion_url,
        insightface_model_path=os.getenv("INSIGHTFACE_MODEL_PATH", "./models/insightface/inswapper_128.onnx"),
        sd_checkpoints_folder=os.getenv("SD_CHECKPOINTS_FOLDER", "C:/AI/ForgeUI/models/Stable-diffusion"),
        image_width=int(os.getenv("IMAGE_WIDTH", "896")),
        image_height=int(os.getenv("IMAGE_HEIGHT", "1152")),
        image_steps=int(os.getenv("IMAGE_STEPS", "30")),
        image_guidance_scale=int(os.getenv("IMAGE_GUIDANCE_SCALE", "4")),
        image_sampler=os.getenv("IMAGE_SAMPLER", "DPM++ 2M SDE"),
        default_sd_model=os.getenv("DEFAULT_SD_MODEL", "lustifySDXLNSFW_ggwpV7.safetensors"),
        epicrealism_sd_model=os.getenv("EPICREALISM_SD_MODEL", "epicrealismXL_vxviiCrystalclear.safetensors"),
        sd_models=sd_models,
        lumina_sd_model=os.getenv("LUMINA_SD_MODEL", "z-image-turbo-q4_k_m.gguf"),
        lumina_vae=os.getenv("LUMINA_VAE", "z_ae.safetensors"),
        lumina_text_encoder=os.getenv("LUMINA_TEXT_ENCODER", "Qwen3-4B-Q4_K_M.gguf"),
        lumina_sampler=os.getenv("LUMINA_SAMPLER", "Euler"),
        lumina_scheduler=os.getenv("LUMINA_SCHEDULER", "beta"),
        lumina_steps=int(os.getenv("LUMINA_STEPS", "8")),
        lumina_cfg_scale=int(os.getenv("LUMINA_CFG_SCALE", "1")),
        lumina_shift=float(os.getenv("LUMINA_SHIFT", "4.0")),
        default_video_duration=int(os.getenv("DEFAULT_VIDEO_DURATION", "10")),
        replicate_api_token=replicate_api_token,
        wavespeed_api_key=wavespeed_api_key,
        wavespeed_api_url=os.getenv("WAVESPEED_API_URL", "https://api.wavespeed.ai/api/v3"),
        civitai_api_token=civitai_api_token,
        hedra_api_key=hedra_api_key,
        hedra_base_url=os.getenv("HEDRA_BASE_URL", "https://mercury.dev.dream-ai.com/api"),
        hedra_headers=hedra_headers,
        zonos_url=os.getenv("ZONOS_URL", "http://localhost:7860"),
        ngrok_auth_token=ngrok_auth_token,
        use_ngrok=bool(use_ngrok),
        remote_password=remote_password,
        api_timeout=int(os.getenv("API_TIMEOUT", "300")),
        api_poll_interval=int(os.getenv("API_POLL_INTERVAL", "1")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_base_delay=float(os.getenv("RETRY_BASE_DELAY", "1.0")),
        max_conversation_history=int(os.getenv("MAX_CONVERSATION_HISTORY", "100")),
        message_chunk_size=int(os.getenv("MESSAGE_CHUNK_SIZE", "2000")),
        max_file_age_days=int(os.getenv("MAX_FILE_AGE_DAYS", "30")),
    )

    return settings


settings = build_settings()


def get_settings(refresh: bool = False) -> Settings:
    if refresh:
        return build_settings()
    return settings

# Backwards-compatible constants
DISCORD_BOT_TOKEN = settings.discord_bot_token
COMMAND_PREFIX = settings.command_prefix

CLAUDE_MODELS = settings.claude_models
OPENROUTER_MODELS = settings.openrouter_models
DEFAULT_LLM = settings.default_llm
DEFAULT_CLAUDE_MODEL = settings.default_claude_model
OPENROUTER_MODEL = settings.default_openrouter_model
OPENROUTER_MAX_TOKENS = settings.openrouter_max_tokens

OPENROUTER_KEY = settings.openrouter_key
OPENROUTER_URL = settings.openrouter_url
OPENROUTER_HEADERS = settings.openrouter_headers

ANTHROPIC_API_KEY = settings.anthropic_api_key
ANTHROPIC_URL = settings.anthropic_url
ANTHROPIC_HEADERS = settings.anthropic_headers
ANTHROPIC_MAX_TOKENS = settings.anthropic_max_tokens

LMSTUDIO_URL = settings.lmstudio_url
LMSTUDIO_HEADERS = settings.lmstudio_headers
LMSTUDIO_MAX_TOKENS = settings.lmstudio_max_tokens

ELEVENLABS_API_KEY = settings.elevenlabs_api_key
ELEVENLABS_TTS_URL = settings.elevenlabs_tts_url
ELEVENLABS_HEADERS = settings.elevenlabs_headers
ELEVENLABS_MODEL_ID = settings.elevenlabs_model_id
ELEVENLABS_VOICE_SETTINGS = settings.elevenlabs_voice_settings
ELEVENLABS_OUTPUT_FORMAT = settings.elevenlabs_output_format

STABLE_DIFFUSION_URL = settings.stable_diffusion_url
INSIGHTFACE_MODEL_PATH = settings.insightface_model_path
SD_CHECKPOINTS_FOLDER = settings.sd_checkpoints_folder

IMAGE_WIDTH = settings.image_width
IMAGE_HEIGHT = settings.image_height
IMAGE_STEPS = settings.image_steps
IMAGE_GUIDANCE_SCALE = settings.image_guidance_scale
IMAGE_SAMPLER = settings.image_sampler
DEFAULT_SD_MODEL = settings.default_sd_model
EPICREALISM_SD_MODEL = settings.epicrealism_sd_model
SD_MODELS = settings.sd_models

LUMINA_SD_MODEL = settings.lumina_sd_model
LUMINA_VAE = settings.lumina_vae
LUMINA_TEXT_ENCODER = settings.lumina_text_encoder
LUMINA_SAMPLER = settings.lumina_sampler
LUMINA_SCHEDULER = settings.lumina_scheduler
LUMINA_STEPS = settings.lumina_steps
LUMINA_CFG_SCALE = settings.lumina_cfg_scale
LUMINA_SHIFT = settings.lumina_shift

DEFAULT_VIDEO_DURATION = settings.default_video_duration

REPLICATE_API_TOKEN = settings.replicate_api_token
WAVESPEED_API_KEY = settings.wavespeed_api_key
WAVESPEED_API_URL = settings.wavespeed_api_url
CIVITAI_API_TOKEN = settings.civitai_api_token
HEDRA_API_KEY = settings.hedra_api_key
HEDRA_BASE_URL = settings.hedra_base_url
HEDRA_HEADERS = settings.hedra_headers
ZONOS_URL = settings.zonos_url

NGROK_AUTH_TOKEN = settings.ngrok_auth_token
USE_NGROK = settings.use_ngrok

API_TIMEOUT = settings.api_timeout
API_POLL_INTERVAL = settings.api_poll_interval
MAX_RETRIES = settings.max_retries
RETRY_BASE_DELAY = settings.retry_base_delay

MAX_CONVERSATION_HISTORY = settings.max_conversation_history
MESSAGE_CHUNK_SIZE = settings.message_chunk_size
MAX_FILE_AGE_DAYS = settings.max_file_age_days

# Import characters after configurations are set
from characters import characters