# Reverie (formerly Discord Dreams)

<p align="center">
  <img src="web/logo.png" alt="Reverie Logo" width="300">
</p>

A powerful, standalone local AI roleplay platform that brings your characters to life with real-time chat, voice synthesis, and multimedia generation.

> **Note**: This is the **Reverie** standalone branch. It operates as a local web server and does not require Discord.

## 🌟 Features

*   **Glassmorphism Premium UI**: A stunning, modern interface featuring glass-effect panels, dynamic gradients, and smooth animations.
*   **Reverie Launcher**: A professional GUI (`launcher.py`) with a cohesive "Slate" theme to manage users, characters, and settings.
*   **Chub.ai Character Import**: One-click import of character cards from Chub.ai with auto-generated image prompts and scenarios.
*   **Multi-LLM Support**: Seamlessly switch between Anthropic (Claude), OpenRouter, and LMStudio models.
*   **Real-Time TTS**: Integrated ElevenLabs Text-to-Speech with auto-play and voice direction.
*   **Script TTS**: Generate TTS from custom scripts, bypassing conversation context.
*   **Multimedia Generation**:
    *   **Selfies**: Generate context-aware images with 12 model options including local SD models (Z-Image Turbo, XL Lustify, EpicRealism, Juggernaut, and more) plus cloud-based Qwen Image 2512 via Replicate.
    *   **Image Editing**: Edit any generated image with natural language instructions using Qwen Image Edit 2511 (e.g., "make her shirt red", "add sunset lighting").
    *   **Videos**: Create short video clips using Replicate or Wavespeed (WAN S2V, InfiniteTalk, Hunyuan Avatar).
    *   **LoRA Videos**: Generate videos with custom LoRA styles using WAN 2.1/2.2 models.
    *   **Lipsync**: Apply lipsync to videos using VEED or Pixverse models.
*   **Story Queue**: Mark images/videos for export, compile into a single concatenated video with FFmpeg.
*   **Face Swap**: ReActor-powered face swap with multiple options:
    *   Automatic face swap on all generated images (unless First-Person mode is on).
    *   "Use Last Frame" on videos automatically applies face swap.
    *   Per-image 🔄 Face button for on-demand face swapping.
*   **Session Resume**: Save and resume chat sessions, preserving conversation history and generated media.
*   **Export Sessions**: Download full sessions as ZIP files with all media and history.
*   **Remote Access**: Securely access your session from other devices on your local network with password protection.
*   **Dynamic Settings**: Adjust system prompts, image prompts, and voice settings directly from the web UI.

## 🛠️ Prerequisites

*   Python 3.10 or higher
*   [FFmpeg](https://ffmpeg.org/download.html) (required for audio processing)
*   API Keys for the services you intend to use:
    *   **LLM**: OpenRouter, Anthropic, or a local LMStudio instance.
    *   **TTS**: ElevenLabs.
    *   **Image/Video**: Replicate (for video), OpenRouter/Local (for images).
    *   **CivitAI** (optional): For CivitAI LoRA URLs.

## 🚀 Installation

1.  **Clone the repository** (if you haven't already).
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    Create a `.env` file in the root directory (use `.env.example` as a template) and add your API keys:
    ```env
    OPENROUTER_KEY=your_key_here
    ANTHROPIC_API_KEY=your_key_here
    ELEVENLABS_API_KEY=your_key_here
    REPLICATE_API_TOKEN=your_key_here
    CIVITAI_API_TOKEN=your_key_here  # Optional, for CivitAI LoRAs
    ```

## 🎮 Usage

1.  **Start the Launcher**:
    ```bash
    python launcher.py
    ```
2.  **Configure & Launch**:
    *   Select a **User** (or add one in `users.py`).
    *   Select a **Character** (defined in `characters.py` or import from Chub.ai).
    *   (Optional) Set a **Remote Password** for network access.
    *   Click **LAUNCH APP**.
3.  **Chat**:
    *   The web interface will open automatically at `http://localhost:8000`.
    *   Start chatting! Use the buttons below the input box to generate selfies or videos.

### Importing Characters from Chub.ai

1.  Download a character card JSON from [Chub.ai](https://chub.ai/).
2.  In the launcher, click **Import Character**.
3.  Select the JSON file and preview the character.
4.  (Optional) Generate a reference image for face swap.
5.  Click **Import Character** to add to your collection.

### Creating Custom Characters

1.  In the launcher, click **Create Character**.
2.  Enter a character name and short description.
3.  Click **Generate Prompts** → LLM generates system prompt and image prompt.
4.  Review and edit the prompts as needed.
5.  Enter an ElevenLabs Voice ID (optional).
6.  Click **Generate Image** to preview the reference image for face swap.
7.  Click **Save Character** to add to your collection.

## 🎬 LoRA Video Generation

Generate videos with custom LoRA styles using the WAN 2.1/2.2 models on Replicate.

### Setup

1.  Copy `lora_presets.example.json` to `lora_presets.json`
2.  Add your LoRA presets with URLs from HuggingFace or CivitAI:
    ```json
    {
        "my_preset": {
            "url": "https://huggingface.co/user/model/resolve/main/lora.safetensors",
            "prompt": "Pre-filled prompt for this LoRA",
            "scale": 1.0,
            "category": "style"
        }
    }
    ```
3.  For CivitAI LoRAs, add `CIVITAI_API_TOKEN` to your `.env` file

### LoRA Categories

LoRAs are organized into tabs by category for easy browsing:
- **Style**: Visual styles (anime, cinematic, etc.)
- **Action**: Movement and dynamic effects
- **Character**: Character-specific LoRAs
- **Other**: Uncategorized LoRAs

You can also mark LoRAs as **Favorites** (⭐) for quick access.

### Usage

1.  Generate an image first (the LoRA video uses the last generated image)
2.  Click the **🎬 LoRA** button
3.  Browse categories or select from Favorites
4.  Adjust frames (81-121) and FPS (5-30)
5.  Click **Generate**

### Backup LoRAs

Use the **📥 Sync to Local** button to download all preset LoRAs to the `custom_loras/` folder for backup.

## 🎞️ Story Queue

Compile multiple images and videos into a single concatenated video.

### Usage

1.  As you generate images and videos during chat, click **➕ Add to Story** on any media
2.  The Story Queue panel appears showing your selected clips
3.  Reorder or remove clips as needed
4.  Click **🎥 Compile Story** when ready - FFmpeg combines them into one video
5.  The queue persists in browser storage, surviving page refreshes

### Face Swap on Frame Extraction

When you click **Use Last Frame** on a video:
1.  The last frame is extracted with FFmpeg
2.  ReActor face swap is automatically applied using your character's source faces
3.  This ensures consistent faces when concatenating multiple video clips

## ⚙️ Configuration

### Characters
Characters are defined in `characters.py`. You can add new characters by adding entries to the `characters` dictionary:

```python
"CharacterName": {
    "system_prompt": "...",
    "image_prompt": "...",
    "tts_url": "...", # ElevenLabs Voice ID URL
    "voice_settings": {
        "stability": 0.4,
        "similarity_boost": 0.45,
        "style": 0.5
    },
    "scenario": "Optional starting scenario..."
}
```

### Public Access (One-Click)
To access the app from anywhere (not just your home WiFi):
1.  Sign up for a free account at [ngrok.com](https://ngrok.com/).
2.  In the **Reverie Launcher**, go to the **LLM Settings** tab and paste your **Ngrok Auth Token**.
3.  On the **Dashboard**, check the **Public Link** box.
4.  Click **LAUNCH APP**. A public `https://...` link will be generated and displayed in the terminal.

## 📂 Project Structure

*   `launcher.py`: Main entry point and control dashboard.
*   `server.py`: FastAPI backend server handling chat and generation logic.
*   `chub_importer.py`: Import and convert Chub.ai character cards.
*   `web/`: Frontend HTML, CSS, and JavaScript files.
*   `characters.py`: Character definitions and configuration.
*   `config.py`: Global configuration and API settings.
*   `lora_presets.json`: Your LoRA preset configurations (gitignored).
*   `lora_presets.example.json`: Template for LoRA presets.
*   `custom_loras/`: Downloaded LoRA files for backup (gitignored).
*   `output/`: Stores generated images, audio, and videos.

## 🤝 Contributing
Feel free to submit issues or pull requests to improve the web app experience!

