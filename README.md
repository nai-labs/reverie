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
*   **Multimedia Generation**:
    *   **Selfies**: Generate context-aware images of your character on demand.
    *   **Videos**: Create short video clips from generated images using Replicate or Wavespeed.
*   **Remote Access**: Securely access your session from other devices on your local network with password protection.
*   **Dynamic Settings**: Adjust system prompts, image prompts, and voice settings directly from the web UI.

## 🛠️ Prerequisites

*   Python 3.10 or higher
*   [FFmpeg](https://ffmpeg.org/download.html) (required for audio processing)
*   API Keys for the services you intend to use:
    *   **LLM**: OpenRouter, Anthropic, or a local LMStudio instance.
    *   **TTS**: ElevenLabs.
    *   **Image/Video**: Replicate (for video), OpenRouter/Local (for images).

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
*   `output/`: Stores generated images, audio, and videos.

## 🤝 Contributing
Feel free to submit issues or pull requests to improve the web app experience!
