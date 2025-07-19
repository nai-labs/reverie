#!/usr/bin/env python3
"""
Discord Dreams Universal Installer
Detects platform and sets up the environment accordingly
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def detect_platform():
    """Detect the current platform"""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    elif system == "Linux":
        if 'microsoft' in platform.uname().release.lower():
            return "wsl"
        else:
            return "linux"
    else:
        return "unknown"

def check_python():
    """Check if Python 3.8+ is available"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("Error: Python 3.8 or higher is required.")
        print(f"Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    return True

def create_virtual_environment(platform_type):
    """Create virtual environment with platform-appropriate paths"""
    print("Creating virtual environment...")
    
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✓ Virtual environment created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create virtual environment: {e}")
        return False

def get_venv_paths(platform_type):
    """Get virtual environment paths for the current platform"""
    if platform_type == "windows":
        return {
            "python": "venv\\Scripts\\python.exe",
            "pip": "venv\\Scripts\\pip.exe",
            "activate": "venv\\Scripts\\activate.bat"
        }
    else:  # Unix-like (macOS, Linux, WSL)
        return {
            "python": "venv/bin/python",
            "pip": "venv/bin/pip",
            "activate": "venv/bin/activate"
        }

def install_requirements(platform_type):
    """Install Python requirements"""
    print("Installing Python requirements...")
    
    venv_paths = get_venv_paths(platform_type)
    
    try:
        subprocess.run([venv_paths["pip"], "install", "-r", "requirements.txt"], check=True)
        print("✓ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install requirements: {e}")
        return False

def get_api_keys():
    """Prompt user for API keys"""
    print("\nPlease enter your API keys:")
    
    keys = {}
    prompts = [
        ("discord_token", "Discord Bot Token"),
        ("discord_user_id", "Discord User ID"),
        ("openrouter_key", "OpenRouter API Key"),
        ("openrouter_referer", "OpenRouter HTTP Referer (https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=YOUR_PERMISSIONS&scope=bot)"),
        ("anthropic_key", "Anthropic API Key"),
        ("elevenlabs_key", "ElevenLabs API Key"),
        ("replicate_token", "Replicate API Token"),
    ]
    
    for key, prompt in prompts:
        value = input(f"{prompt}: ").strip()
        keys[key] = value
    
    return keys

def create_env_file(keys):
    """Create .env file with API keys"""
    print("Creating .env file...")
    
    env_content = f"""DISCORD_BOT_TOKEN={keys['discord_token']}
DISCORD_USER_ID={keys['discord_user_id']}
OPENROUTER_KEY={keys['openrouter_key']}
OPENROUTER_HTTP_REFERER={keys['openrouter_referer']}
ANTHROPIC_API_KEY={keys['anthropic_key']}
ELEVENLABS_API_KEY={keys['elevenlabs_key']}
REPLICATE_API_TOKEN={keys['replicate_token']}
DEFAULT_LLM=anthropic
"""
    
    try:
        with open(".env", "w") as f:
            f.write(env_content)
        print("✓ .env file created successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to create .env file: {e}")
        return False

def setup_characters():
    """Copy characters_example.py to characters.py if it doesn't exist"""
    if not os.path.exists("characters.py"):
        try:
            shutil.copy("characters_example.py", "characters.py")
            print("✓ characters.py created from example")
            return True
        except Exception as e:
            print(f"✗ Failed to create characters.py: {e}")
            return False
    else:
        print("✓ characters.py already exists")
        return True

def print_platform_specific_instructions(platform_type):
    """Print platform-specific usage instructions"""
    venv_paths = get_venv_paths(platform_type)
    
    print(f"\n{'='*60}")
    print("Installation complete!")
    print(f"{'='*60}")
    
    print("\nTo run Discord Dreams, follow these steps:")
    
    if platform_type == "windows":
        print(f"1. Activate the virtual environment: {venv_paths['activate']}")
        print("2. Edit characters.py to add your own characters")
        print("3. Run the launcher: python launcher.py")
        print("   Or run the bot directly: python next.py --user <username> --character <character>")
    
    elif platform_type == "wsl":
        print(f"1. Activate the virtual environment: source {venv_paths['activate']}")
        print("2. Edit characters.py to add your own characters")
        print("3. For GUI launcher (requires X server):")
        print("   - Install VcXsrv or use WSLg if available")
        print("   - Set DISPLAY environment variable if needed")
        print("   - Run: python launcher.py")
        print("4. Or run the bot directly: python next.py --user <username> --character <character>")
        print("\nNote: Audio playback in WSL may require PulseAudio configuration")
    
    elif platform_type in ["macos", "linux"]:
        print(f"1. Activate the virtual environment: source {venv_paths['activate']}")
        print("2. Edit characters.py to add your own characters")
        print("3. Run the launcher: python launcher.py")
        print("   Or run the bot directly: python next.py --user <username> --character <character>")
        
        if platform_type == "macos":
            print("\nNote: You may need to set INSIGHTFACE_MODEL_PATH environment variable")
            print("if you have a local Stable Diffusion setup.")
    
    print(f"\nPlatform detected: {platform_type.upper()}")
    print("Open Discord, and enjoy using Discord Dreams!")

def main():
    print("Discord Dreams Universal Installer")
    print("=" * 40)
    
    # Detect platform
    platform_type = detect_platform()
    print(f"Platform detected: {platform_type.upper()}")
    
    if platform_type == "unknown":
        print("Warning: Unknown platform detected. Proceeding with Unix-like defaults.")
        platform_type = "linux"
    
    # Check Python version
    if not check_python():
        sys.exit(1)
    
    # Create virtual environment
    if not create_virtual_environment(platform_type):
        sys.exit(1)
    
    # Install requirements
    if not install_requirements(platform_type):
        sys.exit(1)
    
    # Get API keys
    keys = get_api_keys()
    
    # Create .env file
    if not create_env_file(keys):
        sys.exit(1)
    
    # Setup characters
    if not setup_characters():
        sys.exit(1)
    
    # Print instructions
    print_platform_specific_instructions(platform_type)

if __name__ == "__main__":
    main()