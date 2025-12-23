import asyncio
import discord
from discord.ext import commands
import aiohttp
import os
import logging
import sys
import argparse
from typing import Optional
from datetime import datetime
from users import get_user_id, list_users
from colorama import Fore

# Character validation function
def validate_character(name: str) -> bool:
    if name not in characters:
        print(f"Error: Character '{name}' not found.")
        print(f"Available characters: {', '.join(characters.keys())}")
        return False
    return True

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run Discord character bot')
    parser.add_argument('--user', required=True, help=f'Username from users.py. Available: {", ".join(list_users())}')
    parser.add_argument('--character', default="Gina", help='Character name to use')
    
    # Add LLM settings arguments
    parser.add_argument('--main-provider', help='Main conversation LLM provider')
    parser.add_argument('--main-model', help='Main conversation model')
    parser.add_argument('--media-provider', help='Media generation LLM provider')
    parser.add_argument('--media-model', help='Media generation model')
    
    args = parser.parse_args()
    
    # Validate character
    if not validate_character(args.character):
        sys.exit(1)
    
    # Validate user
    try:
        args.discord_id = get_user_id(args.user)
    except ValueError as e:
        print(str(e))
        sys.exit(1)
    
    return args

from config import (
    DISCORD_BOT_TOKEN,
    CLAUDE_MODELS,
    OPENROUTER_MODEL,
    ANTHROPIC_MODEL,
    OPENROUTER_MODELS,
    COMMAND_PREFIX,
    LOG_LEVEL,
    LOG_FORMAT
)
from conversation_manager import ConversationManager
from tts_manager import TTSManager
from image_manager import ImageManager
from api_manager import APIManager
from replicate_manager import ReplicateManager
from wavespeed_manager import WavespeedManager

from characters import characters
from status_logger import StatusLogger

# Set up logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logging.getLogger('discord').setLevel(logging.INFO) # Set discord library logging level
logger = logging.getLogger(__name__)

# Set up Discord bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, heartbeat_timeout=60)

# Initialize global variables
# Global state moved to bot instance

@bot.event
async def on_connect():
    """Event handler for when the bot connects to Discord."""
    logger.info("Bot connected to Discord")

@bot.event
async def on_disconnect():
    """Event handler for when the bot disconnects from Discord."""
    logger.warning("Bot disconnected from Discord")

@bot.event
async def on_error(event, *args, **kwargs):
    """Event handler for Discord errors."""
    logger.error(f"Discord error in {event}: {sys.exc_info()[1]}", exc_info=True)

@bot.event
async def on_ready():
    """Event handler for when the bot is ready and connected to Discord."""
    try:
        logger.info(f'Bot is ready. Logged in as {bot.user.name} (ID: {bot.user.id})')
        logger.info(f'Connected to Discord API successfully')
        
        # Get arguments and store in bot instance
        bot.args = parse_args()
        args = bot.args  # Keep local reference for convenience
        logger.info(f"Initializing bot with character '{args.character}' for user '{args.user}' (ID: {args.discord_id})")
        
        # Try to fetch the user
        try:
            user = await bot.fetch_user(bot.args.discord_id)
            logger.info(f"Successfully found user: {user.name} (ID: {user.id})")
        except discord.NotFound:
            logger.error(f"Could not find user with ID {args.discord_id}. Please check the ID in users.py")
            await bot.close()
            return
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch user: {str(e)}")
            await bot.close()
            return
        except Exception as e:
            logger.error(f"Unexpected error fetching user: {str(e)}")
            await bot.close()
            return

        # Initialize managers with selected character
        logger.info("Initializing managers...")
        character_data = characters[args.character]
        bot.conversation_manager = ConversationManager(args.character)
        bot.tts_manager = TTSManager(args.character, bot.conversation_manager)
        


        # Initialize API manager with command-line LLM settings FIRST
        llm_settings = None
        if args.main_provider and args.main_model:
            llm_settings = {
                "main_provider": args.main_provider,
                "main_model": args.main_model,
                "media_provider": args.media_provider,
                "media_model": args.media_model
            }
            logger.info(f"Using command-line LLM settings: {llm_settings}")
        # Store api_manager on the bot instance
        bot.api_manager = APIManager(llm_settings)

        # NOW initialize other managers that might depend on api_manager
        bot.image_manager = ImageManager(bot.conversation_manager, args.character, bot.api_manager) # Pass bot.api_manager
        bot.replicate_manager = ReplicateManager()
        bot.wavespeed_manager = WavespeedManager()



        # Set up log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_name = f"session_{timestamp}"
        bot.conversation_manager.set_log_file(log_file_name)
        logger.info(f"Log file set to: {bot.conversation_manager.log_file}")
        
        # Set status file for launcher
        status_file_path = os.path.join(bot.conversation_manager.subfolder_path, "status.txt")
        StatusLogger.set_status_file(status_file_path)
        StatusLogger.print_success("Bot initialized and ready!")

        bot.initialized = True
        logger.info("Bot initialization complete")
    
        # Send available commands
        logger.info("Sending initial message to user...")
        try:
            await user.send(f"""```md
# ✨ Available Commands ✨

# 🎙️ Core
{COMMAND_PREFIX}say  - Generate a voicenote using ElevenLabs
{COMMAND_PREFIX}pic  - Generate an image based on conversation
{COMMAND_PREFIX}video - Video via Wan S2V (Replicate)
{COMMAND_PREFIX}wavespeed - Video via InfiniteTalk
{COMMAND_PREFIX}video-fast - Video via InfiniteTalk Fast
{COMMAND_PREFIX}video-hunyuan - Video via Hunyuan Avatar

# 🛠️ Conversation
{COMMAND_PREFIX}delete       - Delete the last message
{COMMAND_PREFIX}edit <text>  - Edit the last message
{COMMAND_PREFIX}resume <path>- Resume conversation from log

# ⚙️ Settings & Tools
{COMMAND_PREFIX}narration       - Toggle narration in TTS
{COMMAND_PREFIX}set_voice <id>  - Set ElevenLabs voice ID
{COMMAND_PREFIX}get_voice       - Get current voice ID
{COMMAND_PREFIX}llm             - View/switch LLM settings
{COMMAND_PREFIX}claude          - View/switch Claude models
{COMMAND_PREFIX}openrouter      - View/switch OpenRouter models
{COMMAND_PREFIX}lmstudio        - View/switch LMStudio models
```""")
            logger.info("Initial message sent successfully")
        except discord.Forbidden:
            logger.error(f"Cannot send messages to user {user.name} (ID: {user.id}). Do they share a server with the bot?")
            await bot.close()
            return
        except discord.HTTPException as e:
            logger.error(f"HTTP error sending initial message: {str(e)}")
            await bot.close()
            return
        except Exception as e:
            logger.error(f"Unexpected error sending initial message: {str(e)}")
            await bot.close()
            return

        # Try to send initial character message
        try:
            # Use bot.api_manager
            response_text = await bot.api_manager.generate_response(
                characters[args.character]["scenario"],
                [],  # Empty conversation history
                bot.conversation_manager.system_prompt
            )
            
            if response_text:
                bot.conversation_manager.add_assistant_response(response_text)
                response_chunks = bot.conversation_manager.split_response(response_text)
                for chunk in response_chunks:
                    await user.send(chunk)
                logger.info("Initial character message sent successfully")
        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}", exc_info=True)
            await user.send("I encountered an error while starting the conversation. Please try sending a message.")
            
    except discord.LoginFailure:
        logger.critical("Failed to login to Discord. Please check your token.")
        await bot.close()
    except Exception as e:
        logger.error(f"Critical error in on_ready: {str(e)}", exc_info=True)
        await bot.close()


@bot.event
async def on_message(message):
    """Event handler for incoming messages."""

    if message.author == bot.user:
        return

    # Process commands
    await bot.process_commands(message)

    # Ignore messages that are commands or not from the initiating user
    if message.content.startswith(bot.command_prefix) or message.author.id != bot.args.discord_id:
        return

    # Check if the bot is initialized
    if not getattr(bot, 'initialized', False):
        return

    try:
        # Check for text file attachments
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.endswith('.txt'):
                    file_content = await attachment.read()
                    text_content = file_content.decode('utf-8')
                    # Pass bot instance explicitly
                    await process_message(message, text_content, bot)
                    return  # Exit after processing the first text file

        # If no text file attachment, process the message content as usual
        if message.content:
            # Pass bot instance explicitly
            await process_message(message, message.content, bot)

    except discord.Forbidden:
        logger.error("Bot does not have permission to send messages.")
    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}", exc_info=True)
        try:
            user = await bot.fetch_user(bot.args.discord_id)
            await user.send("I encountered an unexpected error. Please try again later.")
        except:
            pass # If we can't send a message, just log the error

async def process_message(message, content, bot_instance): # Changed parameter to bot_instance
    """Process a message and generate a response."""
    # Check if api_manager exists on the bot instance
    if not hasattr(bot_instance, 'api_manager') or not bot_instance.api_manager:
        logger.error("process_message called but bot_instance.api_manager is not available.")
        user = await bot_instance.fetch_user(args.discord_id) # Use bot_instance here too
        await user.send("Internal error: API Manager not available.")
        return

    api_mgr = bot_instance.api_manager # Get the manager from the bot instance

    try:
        # Handle conversation and generate response using api_mgr
        StatusLogger.print_status("Thinking...", Fore.CYAN)
        response_text = await api_mgr.generate_response(content, bot_instance.conversation_manager.get_conversation(), bot_instance.conversation_manager.system_prompt)

        if response_text:
            bot_instance.conversation_manager.add_user_message(content)
            bot_instance.conversation_manager.add_assistant_response(response_text)

            # Send the response only to the specified user
            user = await bot.fetch_user(bot.args.discord_id)
            response_chunks = bot_instance.conversation_manager.split_response(response_text)
            for chunk in response_chunks:
                await user.send(chunk)
        else:
            user = await bot.fetch_user(bot.args.discord_id)
            await user.send("I apologize, but I couldn't generate a response at this time.")
    
    except aiohttp.ClientError as e:
        logger.error(f"API Error in process_message: {str(e)}", exc_info=True)
        user = await bot.fetch_user(args.discord_id)
        await user.send("I'm having trouble connecting to the AI service. Please try again in a moment.")
    except Exception as e:
        logger.error(f"Error in process_message: {str(e)}", exc_info=True)
        user = await bot.fetch_user(args.discord_id)
        await user.send("I encountered an unexpected error while processing your message. Please try again later.")

# Conversation Management Commands

@bot.command()
async def delete(ctx):
    """Delete the last message in the conversation."""
    deleted_message = ctx.bot.conversation_manager.delete_last_message()
    if deleted_message:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Last message deleted from the conversation.")
        last_message = ctx.bot.conversation_manager.get_last_message()
        if last_message:
            first_three_words = ' '.join(last_message.split()[:3])
            await user.send(f"The new last message starts with: ```{first_three_words}...```")
        else:
            await user.send("The conversation history is now empty.")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("No messages to delete.")

@bot.command()
async def edit(ctx, *, new_content):
    """Edit the last message in the conversation."""
    edited_message = ctx.bot.conversation_manager.edit_last_message(new_content)
    if edited_message:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Last message edited in the conversation.")
        last_message = ctx.bot.conversation_manager.get_last_message()
        first_three_words = ' '.join(last_message.split()[:3])
        await user.send(f"The edited message starts with: ```{first_three_words}...```")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("No messages to edit.")

@bot.command()
async def resume(ctx, directory_path):
    """Resume a conversation from a log file."""
    success = ctx.bot.conversation_manager.resume_conversation(directory_path)
    if success:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Resumed conversation from: {ctx.bot.conversation_manager.log_file}")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Failed to resume conversation. Please check the directory path.")

# TTS Commands

@bot.command()
async def narration(ctx):
    """Toggle narration in TTS."""
    ctx.bot.tts_manager.toggle_narration()
    if ctx.bot.tts_manager.include_narration:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Narration text will be included in the audio.```")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Narration text will be excluded from the audio.```")



@bot.command()
async def set_voice(ctx, voice_id):
    """Set the voice ID for TTS."""
    if ctx.bot.tts_manager.set_voice_id(voice_id):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Voice ID set to: {voice_id}")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Failed to set voice ID.")

@bot.command()
async def get_voice(ctx):
    """Get the current voice ID for TTS."""
    current_voice_id = ctx.bot.tts_manager.get_current_voice_id()
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"Current voice ID: {current_voice_id}")



@bot.command()
async def say(ctx, *, text: Optional[str] = None):
    """Generate a voicenote using ElevenLabs v3 (supports [laughter], etc.)"""
    if not text:
        # Get last message from conversation history
        last_message = ctx.bot.conversation_manager.get_last_message()
        if last_message:
            text = last_message
        else:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("```No preceding message found in the conversation.```")
            return

    # Separate narration (italicized) from dialogue
    import re
    parts = re.split(r'(\*[^*]+\*)', text)
    dialogue_parts = []
    narration_parts = []
    
    for part in parts:
        if part.startswith('*') and part.endswith('*'):
            narration_parts.append(part.strip('*'))
        else:
            if part.strip():
                dialogue_parts.append(part.strip())
                
    dialogue = " ".join(dialogue_parts)
    narration = " ".join(narration_parts)
    
    if not dialogue:
        # If no dialogue found (e.g. only actions), just use the original text as dialogue
        dialogue = text
        narration = ""

    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send("```dreaming up an expressive voicenote...```")

    StatusLogger.print_status("Enhancing text with voice direction...", Fore.CYAN)
    
    # Auto-enhance the text with voice direction tags, passing narration as context
    enhanced_text = await ctx.bot.api_manager.generate_voice_direction(dialogue, narration)
    
    if enhanced_text:
        StatusLogger.print_info(f"Enhanced text: {enhanced_text}")
        # await user.send(f"Enhanced text: {enhanced_text}")
        text = enhanced_text # Use the enhanced text
    else:
        StatusLogger.print_warning("Failed to enhance text, using original.")
        text = dialogue # Fallback to just the dialogue
    
    StatusLogger.print_status("Generating v3 TTS...", Fore.MAGENTA)
    
    # Use the new v3 generation method
    audio_path = await ctx.bot.tts_manager.generate_v3_tts(text)
    
    if audio_path:
        await user.send(f"Generated v3 TTS file: {os.path.basename(audio_path)}", file=discord.File(audio_path))
        ctx.bot.conversation_manager.set_last_audio_path(audio_path)
        StatusLogger.print_success("v3 TTS generated and sent!")
    else:
        await user.send("Failed to generate v3 TTS.")
        StatusLogger.print_error("Failed to generate v3 TTS.")

# Image and Video Commands

@bot.command()
async def pic(ctx):
    """Generate a selfie image using local Stable Diffusion."""
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send("```dreaming up a selfie...```")
    prompt = await ctx.bot.image_manager.generate_selfie_prompt(ctx.bot.conversation_manager.get_conversation())
    image_data = await ctx.bot.image_manager.generate_image(prompt)
    if image_data:
        image_path = await ctx.bot.image_manager.save_image(image_data)
        ctx.bot.conversation_manager.set_last_selfie_path(image_path)
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(file=discord.File(image_path))
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Failed to generate selfie image.")

@bot.command()
async def video(ctx):
    """Generate a video using Wan S2V (requires !pic and !say first)."""
    if not ctx.bot.conversation_manager or not ctx.bot.replicate_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Bot is not fully initialized. Please try again later.")
        return

    # Get last audio and selfie paths
    audio_path = ctx.bot.conversation_manager.get_last_audio_file()
    selfie_path = ctx.bot.conversation_manager.get_last_selfie_path()

    if not audio_path or not selfie_path:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Need both recent audio and selfie. Generate them first using !say and !pic commands.")
        return

    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send("Generating video with Wan S2V... This may take a while.")

    try:
        # Generate prompt using ImageManager (reusing the wan prompt generator)
        prompt = await ctx.bot.image_manager.generate_wan_video_prompt(ctx.bot.conversation_manager.get_conversation())
        
        # Generate the video using ReplicateManager
        video_url = await ctx.bot.replicate_manager.generate_wan_s2v_video(selfie_path, audio_path, prompt)

        if not video_url:
            await user.send("Failed to generate video.")
            return

        # Download and send the video
        await user.send("Downloading generated video...")
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    # Save the video
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_filename = f"wan_s2v_video_{timestamp}.mp4"
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, video_filename)
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    logger.info(f"Wan S2V video saved to: {video_path}")
                    # Send the video file
                    await user.send(file=discord.File(video_path))
                else:
                    logger.error(f"Failed to download video. Status: {resp.status}, URL: {video_url}")
                    await user.send(f"Failed to download the generated video (Status: {resp.status}).")

    except Exception as e:
        logger.error(f"Error in !video command: {e}", exc_info=True)
        await user.send(f"An unexpected error occurred during the !video command: {e}")

@bot.command()
async def wavespeed(ctx):
    """Generate a video using Wavespeed InfiniteTalk (requires !pic and !say first)."""
    if not ctx.bot.conversation_manager or not ctx.bot.wavespeed_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Bot is not fully initialized. Please try again later.")
        return

    # Get last audio and selfie paths
    audio_path = ctx.bot.conversation_manager.get_last_audio_file()
    selfie_path = ctx.bot.conversation_manager.get_last_selfie_path()

    if not audio_path or not selfie_path:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Need both recent audio and selfie. Generate them first using !say and !pic commands.")
        return

    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send("Generating video with Wavespeed InfiniteTalk... This may take a while.")

    try:
        # Generate prompt using ImageManager (reusing the wan prompt generator for expression/pose guidance)
        prompt = await ctx.bot.image_manager.generate_wan_video_prompt(ctx.bot.conversation_manager.get_conversation())
        
        # Generate the video using WavespeedManager
        video_url = await ctx.bot.wavespeed_manager.generate_infinitetalk_video(
            selfie_path, 
            audio_path, 
            prompt=prompt,
            resolution="480p"
        )

        if not video_url:
            await user.send("Failed to generate video.")
            return

        # Download and send the video
        await user.send("Downloading generated video...")
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    # Save the video
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_filename = f"wavespeed_video_{timestamp}.mp4"
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, video_filename)
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    logger.info(f"Wavespeed video saved to: {video_path}")
                    # Send the video file
                    await user.send(file=discord.File(video_path))
                else:
                    logger.error(f"Failed to download video. Status: {resp.status}, URL: {video_url}")
                    await user.send(f"Failed to download the generated video (Status: {resp.status}).")

    except Exception as e:
        logger.error(f"Error in !wavespeed command: {e}", exc_info=True)
        await user.send(f"An unexpected error occurred during the !wavespeed command: {e}")

async def _generate_wavespeed_video(ctx, model: str, model_name: str):
    """Helper function to generate video with any Wavespeed model."""
    if not ctx.bot.conversation_manager or not ctx.bot.wavespeed_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Bot is not fully initialized. Please try again later.")
        return

    audio_path = ctx.bot.conversation_manager.get_last_audio_file()
    selfie_path = ctx.bot.conversation_manager.get_last_selfie_path()

    if not audio_path or not selfie_path:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Need both recent audio and selfie. Generate them first using !say and !pic commands.")
        return

    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"Generating video with {model_name}... This may take a while.")

    try:
        prompt = await ctx.bot.image_manager.generate_wan_video_prompt(ctx.bot.conversation_manager.get_conversation())
        
        video_url = await ctx.bot.wavespeed_manager.generate_video(
            selfie_path, 
            audio_path,
            model=model,
            prompt=prompt,
            resolution="480p"
        )

        if not video_url:
            await user.send("Failed to generate video.")
            return

        await user.send("Downloading generated video...")
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_filename = f"{model}_video_{timestamp}.mp4"
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, video_filename)
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    logger.info(f"{model_name} video saved to: {video_path}")
                    await user.send(file=discord.File(video_path))
                else:
                    logger.error(f"Failed to download video. Status: {resp.status}, URL: {video_url}")
                    await user.send(f"Failed to download the generated video (Status: {resp.status}).")

    except Exception as e:
        logger.error(f"Error in {model_name} video command: {e}", exc_info=True)
        await user.send(f"An unexpected error occurred: {e}")

@bot.command(name="video-fast")
async def video_fast(ctx):
    """Generate a video using Wavespeed InfiniteTalk Fast (faster, slightly lower quality)."""
    await _generate_wavespeed_video(ctx, "infinitetalk-fast", "InfiniteTalk Fast")

@bot.command(name="video-hunyuan")
async def video_hunyuan(ctx):
    """Generate a video using Hunyuan Avatar (emotion-aware, max 2 min)."""
    await _generate_wavespeed_video(ctx, "hunyuan-avatar", "Hunyuan Avatar")

# Replicate Manager Commands

@bot.command()
async def test_replicate(ctx):
    """Test Replicate API authentication."""
    if not ctx.bot.replicate_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Replicate manager is not initialized.")
        return
    
    auth_result = await ctx.bot.replicate_manager.test_auth()
    if auth_result:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Replicate authentication successful!")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Replicate authentication failed. Please check your API token.")

@bot.command()
async def set_expression(ctx, value: float):
    """Set the expression scale for the talking face generation."""
    result = ctx.bot.replicate_manager.set_expression_scale(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

@bot.command()
async def set_pose(ctx, value: int):
    """Set the pose style for the talking face generation."""
    result = ctx.bot.replicate_manager.set_pose_style(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

@bot.command()
async def set_facerender(ctx, value: str):
    """Set the face render method for the talking face generation."""
    result = ctx.bot.replicate_manager.set_facerender(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

@bot.command()
async def set_preprocess(ctx, value: str):
    """Set the preprocess method for the talking face generation."""
    result = ctx.bot.replicate_manager.set_preprocess(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

@bot.command()
async def set_still_mode(ctx, value: str):
    """Set the still mode for the talking face generation."""
    result = ctx.bot.replicate_manager.set_still_mode(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

@bot.command()
async def set_use_enhancer(ctx, value: str):
    """Set whether to use enhancer for the talking face generation."""
    result = ctx.bot.replicate_manager.set_use_enhancer(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

@bot.command()
async def set_use_eyeblink(ctx, value: str):
    """Set whether to use eye blink for the talking face generation."""
    result = ctx.bot.replicate_manager.set_use_eyeblink(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

@bot.command()
async def set_size_of_image(ctx, value: int):
    """Set the size of the image for the talking face generation."""
    result = ctx.bot.replicate_manager.set_size_of_image(value)
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(result)

# LLM and Model Commands

@bot.command()
async def claude(ctx, model_code=None):
    """Switch or view Claude models."""
    if model_code is None:
        current_model = ctx.bot.api_manager.get_current_model()
        available_models = ", ".join([f"{full_name} ({short_code})" for full_name, short_code in CLAUDE_MODELS.items()])
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Current Claude model: {current_model}\nAvailable models: {available_models}")
    elif ctx.bot.api_manager.switch_claude_model(model_code):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Switched to Claude model: {ctx.bot.api_manager.get_current_model()}")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Invalid Claude model code. Available models: {', '.join(CLAUDE_MODELS.values())}")

@bot.command()
async def openrouter(ctx, model_code=None):
    """Switch or view OpenRouter models."""
    if model_code is None:
        current_model = ctx.bot.api_manager.get_current_model()
        available_models = ", ".join([f"{full_name} ({short_code})" for full_name, short_code in OPENROUTER_MODELS.items()])
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Current OpenRouter model: {current_model}\nAvailable models: {available_models}")
    elif ctx.bot.api_manager.switch_openrouter_model(model_code):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Switched to OpenRouter model: {ctx.bot.api_manager.get_current_model()}")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Invalid OpenRouter model code. Available models: {', '.join(OPENROUTER_MODELS.values())}")

@bot.command()
async def lmstudio(ctx, model_name=None):
    """Switch or view LMStudio models."""
    if model_name is None:
        models = await ctx.bot.api_manager.fetch_lmstudio_models()
        if models:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send(f"Available LMStudio models: {', '.join(models)}")
        else:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("No LMStudio models available or couldn't fetch the list.")
    elif ctx.bot.api_manager.set_lmstudio_model(model_name):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Switched to LMStudio model: {model_name}")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Failed to switch to LMStudio model: {model_name}")

@bot.command()
async def llm(ctx, llm_name=None):
    """Switch or view current LLM and model."""
    if llm_name is None:
        current_llm = ctx.bot.api_manager.get_current_llm()
        current_model = ctx.bot.api_manager.get_current_model()
        available_llms = "anthropic, openrouter, lmstudio"
        
        response = f"Current LLM: {current_llm}\n"
        response += f"Current Model: {current_model}\n\n"
        response += f"Available LLMs: {available_llms}\n"
        response += f"Use '{COMMAND_PREFIX}llm <llm_name>' to switch LLMs.\n"
        response += f"Use '{COMMAND_PREFIX}claude', '{COMMAND_PREFIX}openrouter', or '{COMMAND_PREFIX}lmstudio' to see or switch specific models."
        
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"```{response}```")

if __name__ == "__main__":
    logger.info("Starting next.py")
    try:
        # Verify bot token
        if not DISCORD_BOT_TOKEN:
            logger.error("DISCORD_BOT_TOKEN is not set in environment variables")
            sys.exit(1)
        if len(DISCORD_BOT_TOKEN) < 50:  # Discord tokens are typically longer
            logger.error("DISCORD_BOT_TOKEN appears to be invalid (too short)")
            sys.exit(1)
            
        logger.info("Starting Discord bot...")
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)  # Disable Discord's logging to use our own
    except discord.LoginFailure as error:
        logger.error(f"Failed to log in to Discord: {str(error)}")
        logger.error("Please check your bot token")
        sys.exit(1)
    except discord.HTTPException as error:
        logger.error(f"HTTP error connecting to Discord: {str(error)}")
        sys.exit(1)
    except Exception as error:
        logger.error(f"An unexpected error occurred: {str(error)}", exc_info=True)
        sys.exit(1)
