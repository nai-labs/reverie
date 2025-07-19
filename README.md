# Discord Dreams

A Discord bot framework for creating AI characters with multimodal capabilities including text conversation, voice synthesis, image generation, and video generation.

## Overview

Discord Dreams enables the creation of AI characters that can:
- Engage in natural conversations using various LLM providers (Claude, OpenRouter, LMStudio)
- Generate voice responses with character-specific TTS (ElevenLabs and Zonos)
- Create contextual images based on conversation (Stable Diffusion and Replicate)
- Generate animated videos with lip sync (Replicate and Hedra)
- Maintain conversation history and character personas

## Setup

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Required API Keys:
  - Anthropic (Claude) or OpenRouter API key
  - Replicate API key (for image/video generation)
  - ElevenLabs API key (for TTS)
  - Hedra API key (for video generation)

### Installation

#### Option 1: Universal Installer (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd discord-dreams
```

2. Run the universal installer:
```bash
python install.py
```

The installer will:
- Detect your platform (Windows/WSL/macOS/Linux)
- Create a virtual environment
- Install dependencies
- Prompt for API keys
- Set up configuration files
- Provide platform-specific instructions

#### Option 2: Manual Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd discord-dreams
```

2. Create and activate virtual environment:

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**WSL/macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables in `.env`:
```env
DISCORD_BOT_TOKEN=your_discord_bot_token
ANTHROPIC_API_KEY=your_anthropic_key
OPENROUTER_API_KEY=your_openrouter_key
REPLICATE_API_TOKEN=your_replicate_token
ELEVENLABS_API_KEY=your_elevenlabs_key
HEDRA_API_KEY=your_hedra_key
# INSIGHTFACE_MODEL_PATH is auto-detected based on platform
# Set manually only if you have a custom path
```

5. Configure characters in `characters.py` (see `characters_example.py` for template)

5. Configure users in `users.py`

## Core Components

### Launcher (launcher.py)
- GUI interface for managing bot instances
- Character/user selection
- LLM provider configuration
- Process monitoring
- Conversation viewing

### Character System (characters.py)
- Character definitions
- System prompts
- Voice settings
- Image generation settings
- Scenario configuration

### Conversation Management (conversation_manager.py)
- Message history tracking
- Log file management
- Context maintenance
- Message formatting

### Media Generation
- **TTS (tts_manager.py)**: Voice synthesis using ElevenLabs
- **TTS (zonos_manager.py)**: Voice synthesis using a local Zonos server
- **Images (image_manager.py)**: Selfie generation using Stable Diffusion
- **Videos (replicate_manager.py)**: Video generation using various Replicate models (Kling, LatentSync, WAN)
- **Videos (hedra_manager.py)**: Video generation using the Hedra API

### API Integration (api_manager.py)
- LLM provider management
- Model switching
- API call handling
- Response processing

## Usage

### Running the Bot

1. Launch the GUI:
```bash
python launcher.py
```

2. Select a user and character
3. Configure LLM settings if needed
4. Click "Deploy Bot"

### Available Commands

- `!say` - Generate TTS for the last message using ElevenLabs
- `!speak` - Generate TTS for the last message using Zonos
- `!pic` - Generate a contextual image using Stable Diffusion
- `!klingat` - Generate a video with lip sync using Replicate's Kling and LatentSync models
- `!hedra` - Generate a video with lip sync using Hedra
- `!wan` - Generate a video from an image using Replicate's WAN I2V model
- `!delete` - Delete the last message
- `!edit <text>` - Edit the last message
- `!resume <path>` - Resume a previous conversation

### LLM Commands

- `!claude <model>` - Switch Claude models
- `!openrouter <model>` - Switch OpenRouter models
- `!lmstudio <model>` - Switch LMStudio models
- `!llm` - View current LLM settings

### Zonos TTS Settings

- `!set_emotion <emotion> <value>` - Set emotion for Zonos TTS (e.g., `!set_emotion happy 0.8`)
- `!set_quality <value>` - Set voice quality for Zonos TTS (0.5-0.8)
- `!set_speed <value>` - Set speaking rate for Zonos TTS (5-30)
- `!set_pitch <value>` - Set pitch variation for Zonos TTS (0-300)

### Video Generation Settings

- `!set_expression <value>` - Set expression scale
- `!set_pose <value>` - Set pose style
- `!set_facerender <method>` - Set face render method
- `!set_still_mode <true/false>` - Toggle still mode
- `!set_use_enhancer <true/false>` - Toggle enhancer
- `!set_use_eyeblink <true/false>` - Toggle eye blinking

## Platform-Specific Considerations

### Windows
- Audio playback uses `winsound` by default
- All features should work out of the box
- Virtual environment: `venv\Scripts\activate.bat`

### WSL (Windows Subsystem for Linux)
- **GUI Requirements**: The launcher GUI requires an X server:
  - **WSLg** (Windows 11): Usually works automatically
  - **VcXsrv** (Windows 10): Install and configure X server
  - Set `DISPLAY` environment variable if needed: `export DISPLAY=:0`
- **Audio**: May require PulseAudio configuration for audio playback
- **Paths**: Windows drives accessible at `/mnt/c/`, `/mnt/d/`, etc.
- **Dependencies**: Uses pygame/playsound for audio instead of winsound
- Virtual environment: `source venv/bin/activate`

### macOS
- Audio playback uses pygame/playsound
- **Homebrew recommended** for system dependencies
- **INSIGHTFACE_MODEL_PATH**: Must be set manually if using Stable Diffusion
- Virtual environment: `source venv/bin/activate`
- **Python**: Use `python3` instead of `python` if needed

### Linux
- Audio playback uses pygame/playsound
- **System packages**: May need to install audio libraries:
  ```bash
  sudo apt-get install python3-dev libasound2-dev  # Ubuntu/Debian
  sudo dnf install python3-devel alsa-lib-devel    # Fedora
  ```
- **INSIGHTFACE_MODEL_PATH**: Must be set manually if using Stable Diffusion
- Virtual environment: `source venv/bin/activate`

### Troubleshooting

#### Audio Issues
1. **No audio playback**: Check if pygame or playsound is installed
2. **WSL audio**: Configure PulseAudio or use Windows-side audio
3. **Permission errors**: Ensure audio devices are accessible

#### GUI Issues
1. **WSL GUI not working**:
   - Install VcXsrv or enable WSLg
   - Set `DISPLAY=:0` in your environment
   - Check firewall settings for X server connections
2. **Font rendering issues**: Install system fonts or adjust tkinter settings

#### Path Issues
1. **INSIGHTFACE_MODEL_PATH**: Set environment variable for custom paths
2. **WSL path mapping**: Use `/mnt/c/...` format for Windows drives
3. **File permissions**: Ensure read/write access to output directories

## Development Guide

### Project Structure

```
discord-dreams/
├── launcher.py          # GUI application
├── next.py             # Main bot implementation
├── characters.py       # Character definitions
├── users.py           # User configurations
├── config.py          # Global configuration
├── api_manager.py     # LLM API handling
├── conversation_manager.py  # Message management
├── image_manager.py   # Image generation
├── tts_manager.py     # ElevenLabs TTS
├── zonos_manager.py   # Zonos TTS
├── replicate_manager.py    # Replicate API for video/image
├── hedra_manager.py      # Hedra API for video
└── output/            # Generated media storage
```

### Key Files

- **next.py**: Core bot implementation with command handling and event processing
- **launcher.py**: GUI interface for bot management and monitoring
- **characters.py**: Character definitions including prompts and settings
- **conversation_manager.py**: Handles message history and logging
- **image_manager.py**: Manages image generation with context awareness
- **tts_manager.py**: Handles voice synthesis with ElevenLabs
- **zonos_manager.py**: Handles voice synthesis with a local Zonos server
- **replicate_manager.py**: Manages video and image generation with the Replicate API
- **hedra_manager.py**: Manages video generation with the Hedra API
- **api_manager.py**: Handles LLM provider integration and switching

### Common Customization Points

1. Character Creation
   - Add a new character in `characters.py`
   - Configure system prompt, voice, and image settings
   - Set up a scenario and initial context

2. Adding Commands
   - Extend command handlers in `next.py`
   - Follow existing command patterns
   - Update help documentation

3. Media Generation
   - Modify prompt generation in `image_manager.py`
   - Adjust video settings in `replicate_manager.py`
   - Configure TTS parameters in `tts_manager.py` or `zonos_manager.py`

4. LLM Integration
   - Add new providers in `api_manager.py`
   - Configure model settings in `config.py`
   - Implement provider-specific handling

### Best Practices

1. Error Handling
   - Use try/except blocks for API calls
   - Provide meaningful error messages
   - Log errors for debugging

2. Resource Management
   - Clean up temporary files
   - Close connections properly
   - Monitor memory usage

3. Configuration
   - Use environment variables for sensitive data
   - Keep configuration in appropriate files
   - Document required settings

4. Testing
   - Test new features with `test_*.py` files
   - Verify API integrations
   - Check resource cleanup

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

See the LICENSE file for details.
