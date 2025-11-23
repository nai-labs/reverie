# Discord Dreams

**Discord Dreams** is a modular Discord bot framework designed for creating immersive, multimodal AI characters. It integrates advanced Large Language Models (LLMs), Text-to-Speech (TTS), Image Generation, and Video Generation services to bring characters to life with distinct personalities, voices, and visual presence.

## 🌟 Features

*   **Multimodal Interaction**: Characters can reply with text, voice notes, selfies, and even video messages.
*   **Flexible LLM Support**:
    *   **Anthropic (Claude)**: High-quality character roleplay.
    *   **OpenRouter**: Access to a wide range of models (DeepSeek, Mistral, Llama, etc.).
    *   **LMStudio**: Local LLM support for privacy and cost savings.
*   **Advanced Voice Synthesis**:
    *   **ElevenLabs**: Premium, realistic cloud-based TTS.
    *   **Zonos**: Support for local Zonos TTS servers for high-quality, controllable voice generation.
*   **Visual Generation**:
    *   **Stable Diffusion (Automatic1111/Forge)**: Generates contextual "selfies" based on the conversation.
    *   **Replicate**: Integrates with state-of-the-art models like **Kling**, **LatentSync**, **WAN**, and **SadTalker** for video generation and lip-syncing.
    *   **Hedra**: specialized character video generation.
*   **User-Friendly Launcher**: A GUI (`launcher.py`) to easily manage bot instances, select characters, configure models, and monitor conversations in real-time.
*   **Conversation Management**: Maintains context-aware history, supports editing/deleting messages, and logging.

## 🛠️ Architecture

The project is organized into modular managers to handle specific capabilities:

*   **`launcher.py`**: The entry point for the GUI. Manages bot processes and configuration.
*   **`next.py`**: The core bot logic using `discord.py`. Handles events and commands.
*   **`api_manager.py`**: Unified interface for LLM providers (Anthropic, OpenRouter, LMStudio).
*   **`conversation_manager.py`**: Handles message history, context, and logging.
*   **`image_manager.py`**: Generates image prompts via LLM and interfaces with a local Stable Diffusion API.
*   **`tts_manager.py`**: Handles ElevenLabs TTS.
*   **`zonos_manager.py`**: Handles local Zonos TTS.
*   **`replicate_manager.py`**: Manages video/image generation jobs on Replicate.
*   **`hedra_manager.py`**: Interface for Hedra video generation.
*   **`characters.py`**: (User-defined) Stores character profiles, prompts, and settings.

## 🚀 Setup & Installation

### Prerequisites

*   **Python 3.10+**
*   **Discord Bot Token**: Create one at the [Discord Developer Portal](https://discord.com/developers/applications).
*   **API Keys** (depending on features used):
    *   Anthropic / OpenRouter (for LLM)
    *   ElevenLabs (for cloud TTS)
    *   Replicate (for video/image generation)
    *   Hedra (optional, for video)
*   **Local Services** (optional):
    *   **Stable Diffusion (Automatic1111/Forge)**: Running with `--api` flag.
    *   **LMStudio**: Running local server.
    *   **Zonos**: Running local TTS server.

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/discord-dreams.git
    cd discord-dreams
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    *   Copy `.env.example` to `.env` (if available) or create a `.env` file with your keys:
        ```env
        DISCORD_BOT_TOKEN=your_token_here
        ANTHROPIC_API_KEY=your_key_here
        OPENROUTER_KEY=your_key_here
        REPLICATE_API_TOKEN=r8_your_token_here
        ELEVENLABS_API_KEY=your_key_here
        HEDRA_API_KEY=your_key_here
        # Optional Local URLs
        ZONOS_URL=http://localhost:7860
        INSIGHTFACE_MODEL_PATH=C:/path/to/inswapper_128.onnx
        ```

4.  **Define Characters**:
    *   Create a `characters.py` file (use `characters_example.py` as a template).
    *   Define your characters with their system prompts, voice settings, and image prompts.

5.  **Define Users**:
    *   Update `users.py` with authorized Discord user IDs.

### Running the Bot

**Using the GUI (Recommended):**
```bash
python launcher.py
```
*   Select your User and Character.
*   Choose your Main LLM and Media LLM providers.
*   Click **Deploy Bot**.
*   Use the "Process Monitor" to stop bots or view logs.

**Command Line:**
```bash
python next.py --user <username> --character <character_name>
```

## 💬 Commands

*   `!say [text]` - Generate a voice note (uses last message if text is empty).
*   `!pic` - Generate a contextual selfie.
*   `!klingat` - Generate a video using Kling + LatentSync (requires recent audio & image).
*   `!hedra` - Generate a video using Hedra.
*   `!wan` - Generate a video using WAN model.
*   `!delete` - Delete the last message from memory.
*   `!edit <text>` - Edit the last message in memory.
*   `!resume <folder_name>` - Resume a conversation from a log folder.
*   `!speak` - (Zonos) Generate TTS using local Zonos server.

## 📝 License

[MIT License](LICENSE)
