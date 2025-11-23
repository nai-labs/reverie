# next.py
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
from hedra_manager import HedraManager
from zonos_manager import ZonosManager
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
    # global conversation_manager, tts_manager, zonos_manager, image_manager, replicate_manager, hedra_manager, bot_initialized, args
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
        
        # Try to initialize Zonos, but continue if it fails
        try:
            logger.info("Attempting to initialize Zonos manager...")
            bot.zonos_manager = ZonosManager(args.character, bot.conversation_manager)
            logger.info("Zonos manager initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Zonos manager: {str(e)}")
            logger.warning("Bot will continue without Zonos TTS functionality")
            bot.zonos_manager = None

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

        # Try to initialize Hedra, but continue if it fails
        try:
            logger.info("Attempting to initialize Hedra manager...")
            bot.hedra_manager = HedraManager()
            logger.info("Hedra manager initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Hedra manager: {str(e)}")
            logger.warning("Bot will continue without Hedra video functionality")
            bot.hedra_manager = None

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
            await user.send(f"""```Available commands:
{COMMAND_PREFIX}say - Generate a voicenote using ElevenLabs
{COMMAND_PREFIX}pic - Generate an image based on this point in the conversation
{COMMAND_PREFIX}klingat - Generate a video using Kling and LatentSync
{COMMAND_PREFIX}hedra - Generate a video using Hedra
{COMMAND_PREFIX}wan - Generate a video using the WAN I2V model (requires !pic first)


```""")
            
# Optional Zonos TTS Commands (when server is available):
# {COMMAND_PREFIX}speak - Generate a voicenote using local Zonos server
# {COMMAND_PREFIX}test_zonos - Test connection to Zonos server
# {COMMAND_PREFIX}set_emotion <emotion> <value> - Set emotion (e.g. happy 0.8)
# {COMMAND_PREFIX}set_quality <value> - Set voice quality (0.5-0.8)
# {COMMAND_PREFIX}set_speed <value> - Set speaking rate (5-30)
# {COMMAND_PREFIX}set_pitch <value> - Set pitch variation (0-300)
# {COMMAND_PREFIX}set_voice_sample <path> - Set voice sample for cloning
# {COMMAND_PREFIX}show_zonos_settings - Show current Zonos settings
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
    # Removed api_manager from globals list
    # global bot_initialized, conversation_manager, tts_manager, zonos_manager, args

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
async def say(ctx):
    """Generate TTS for the last message or specified text."""
    command_text = ctx.message.content[len(f'{COMMAND_PREFIX}say'):].strip()
    if command_text:
        tts_text = command_text
    else:
        last_message = ctx.bot.conversation_manager.get_last_message()
        if last_message:
            tts_text = ctx.bot.tts_manager.get_tts_text(last_message)
        else:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("No preceding message found in the conversation.")
            return

    await ctx.bot.tts_manager.send_tts_file(ctx, tts_text)

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

# Zonos TTS Commands
@bot.command()
async def set_emotion(ctx, emotion: str, value: float):
    """Set emotion value for Zonos TTS (0-1)."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    emotion_map = {
        "happy": "e1", "happiness": "e1",
        "sad": "e2", "sadness": "e2",
        "disgust": "e3",
        "fear": "e4",
        "surprise": "e5",
        "anger": "e6", "angry": "e6",
        "other": "e7",
        "neutral": "e8"
    }
    
    if emotion.lower() not in emotion_map:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"```Invalid emotion. Available emotions: {', '.join(set(emotion_map.keys()))}```")
        return
        
    if not 0 <= value <= 1:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Emotion value must be between 0 and 1```")
        return
        
    emotion_key = emotion_map[emotion.lower()]
    ctx.bot.zonos_manager.settings[emotion_key] = value
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"```Set {emotion} to {value}```")

@bot.command()
async def set_quality(ctx, value: float):
    """Set voice quality for Zonos TTS (0.5-0.8)."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    if not 0.5 <= value <= 0.8:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Quality value must be between 0.5 and 0.8```")
        return
        
    ctx.bot.zonos_manager.settings["vq_single"] = value
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"```Set voice quality to {value}```")

@bot.command()
async def set_speed(ctx, value: float):
    """Set speaking rate for Zonos TTS (5-30)."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    if not 5 <= value <= 30:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Speaking rate must be between 5 and 30```")
        return
        
    ctx.bot.zonos_manager.settings["speaking_rate"] = value
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"```Set speaking rate to {value}```")

@bot.command()
async def set_pitch(ctx, value: float):
    """Set pitch variation for Zonos TTS (0-300)."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    if not 0 <= value <= 300:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Pitch variation must be between 0 and 300```")
        return
        
    ctx.bot.zonos_manager.settings["pitch_std"] = value
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"```Set pitch variation to {value}```")

@bot.command()
async def set_voice_sample(ctx, path: str):
    """Set voice sample file for Zonos TTS voice cloning."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    if not os.path.exists(path):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"```Voice sample file not found at: {path}```")
        return
        
    ctx.bot.zonos_manager.speaker_audio = path
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"```Set voice sample to: {path}```")

@bot.command()
async def test_zonos(ctx):
    """Test connection to Zonos server."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    try:
        # Try to connect to Zonos server
        logger.info(f"Testing Zonos server connection at {ZONOS_URL}...")
        async with aiohttp.ClientSession() as session:
            async with session.get(ZONOS_URL) as response:
                if response.status == 200:
                    await user.send("✅ Successfully connected to Zonos server!")
                    content_type = response.headers.get('content-type', 'unknown')
                    server = response.headers.get('server', 'unknown')
                    await user.send("```Server Status:\n" + 
                                  f"- URL: {ZONOS_URL}\n" +
                                  "- Status Code: 200 OK\n" +
                                  f"- Content Type: {content_type}\n" +
                                  f"- Server: {server}\n" +
                                  f"- Model: {ctx.bot.zonos_manager.settings['model_choice']}\n" +
                                  "- Server is ready to generate audio```")
                else:
                    await user.send(f"```❌ Server responded with status code: {response.status}\n" +
                                  f"Response headers: {dict(response.headers)}```")
            
    except Exception as e:
        logger.error(f"Failed to connect to Zonos server: {str(e)}")
        await user.send(f"```❌ Failed to connect to Zonos server: {str(e)}```")

@bot.command()
async def show_zonos_settings(ctx):
    """Show current Zonos TTS settings."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    settings = ctx.bot.zonos_manager.settings
    response = "Current Zonos Settings:\n"
    response += f"Model: {settings['model_choice']}\n"
    response += f"Language: {settings['language']}\n"
    response += f"Voice Quality: {settings['vq_single']}\n"
    response += f"Speaking Rate: {settings['speaking_rate']}\n"
    response += f"Pitch Variation: {settings['pitch_std']}\n"
    response += "\nEmotions:\n"
    response += f"Happiness: {settings['e1']}\n"
    response += f"Sadness: {settings['e2']}\n"
    response += f"Disgust: {settings['e3']}\n"
    response += f"Fear: {settings['e4']}\n"
    response += f"Surprise: {settings['e5']}\n"
    response += f"Anger: {settings['e6']}\n"
    response += f"Other: {settings['e7']}\n"
    response += f"Neutral: {settings['e8']}\n"
    response += f"\nVoice Sample: {ctx.bot.zonos_manager.speaker_audio if ctx.bot.zonos_manager.speaker_audio else 'None'}"
    
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send(f"```{response}```")

@bot.command()
async def speak(ctx):
    """Generate TTS using local Zonos server."""
    if not ctx.bot.zonos_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("```Zonos TTS is not currently available```")
        return
        
    try:
        logger.debug("Starting speak command")
        logger.debug(f"Conversation manager initialized: {ctx.bot.conversation_manager is not None}")
        logger.debug(f"Zonos manager initialized: {ctx.bot.zonos_manager is not None}")
        
        command_text = ctx.message.content[len(f'{COMMAND_PREFIX}speak'):].strip()
        logger.debug(f"Command text: '{command_text}'")
        
        if command_text:
            tts_text = command_text
            logger.debug("Using direct command text")
        else:
            logger.debug("No command text, checking conversation history")
            last_message = ctx.bot.conversation_manager.get_last_message()
            if last_message:
                tts_text = ctx.bot.zonos_manager.get_tts_text(last_message)
                logger.debug(f"Using last message: '{tts_text}'")
            else:
                logger.debug("No last message found")
                user = await bot.fetch_user(ctx.bot.args.discord_id)
                await user.send("```No preceding message found in the conversation.```")
                return

        # Check output directory
        output_dir = os.path.join(os.getcwd(), 'output')
        logger.debug(f"Output directory: {output_dir}")
        logger.debug(f"Output directory exists: {os.path.exists(output_dir)}")
        if not os.path.exists(output_dir):
            logger.debug("Creating output directory")
            os.makedirs(output_dir)

        await ctx.bot.zonos_manager.send_tts_file(ctx, tts_text)
        
    except Exception as e:
        logger.error(f"Error in speak command: {str(e)}", exc_info=True)
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"```❌ Error in speak command: {str(e)}```")

# Image and Video Commands

@bot.command()
async def image(ctx):
    """Generate an image using Replicate's recraft-v3 model."""
    try:
        prompt = await ctx.bot.image_manager.generate_selfie_prompt(ctx.bot.conversation_manager.get_conversation())
        if prompt:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("Generating image with Replicate... This may take a while.")
            StatusLogger.print_status("Generating image...", Fore.YELLOW)
            image_url = await ctx.bot.replicate_manager.generate_image(prompt)
            if image_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                            image_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, "replicate_image.webp")
                            with open(image_path, "wb") as f:
                                f.write(image_data)
                            ctx.bot.conversation_manager.set_last_selfie_path(image_path)
                            user = await bot.fetch_user(ctx.bot.args.discord_id)
                            await user.send(file=discord.File(image_path))
                            StatusLogger.print_success("Image generated and sent!")
                        else:
                            user = await bot.fetch_user(ctx.bot.args.discord_id)
                            await user.send(f"Failed to download the generated image. Status code: {resp.status}")
                            StatusLogger.print_error("Failed to download image.")
            else:
                user = await bot.fetch_user(ctx.bot.args.discord_id)
                await user.send("Failed to generate image with Replicate.")
        else:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("Failed to generate image prompt.")

    except aiohttp.ClientError as e:
        logger.error(f"Network error in image command: {e}")
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Network error while generating image: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in image command: {e}", exc_info=True)
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"An unexpected error occurred: {str(e)}")

@bot.command()
async def pic(ctx):
    """Generate a selfie image using local Stable Diffusion."""
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
    """Generate a video using the last audio and character's input video."""
    if not ctx.bot.conversation_manager or not ctx.bot.replicate_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Bot is not fully initialized. Please try again later.")
        return

    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send("Generating video... This may take a while.")

    face_path = characters[ctx.bot.conversation_manager.character_name].get("input_video")
    if not face_path or not os.path.exists(face_path):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Input video not found at path: {face_path}")
        return

    audio_path = ctx.bot.conversation_manager.get_last_audio_file()
    if not audio_path:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("No recent audio file found.")
        return

    try:
        output = await asyncio.create_task(ctx.bot.replicate_manager.generate_video_retalking(face_path, audio_path))

        if output is None:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("Failed to generate the video. Please check the logs for more details.")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(output) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, "retalking_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    
                    user = await bot.fetch_user(ctx.bot.args.discord_id)
                    await user.send("Here's the generated video:", file=discord.File(video_path))
                else:
                    user = await bot.fetch_user(ctx.bot.args.discord_id)
                    await user.send(f"Failed to download the generated video. Status code: {resp.status}")
    except Exception as e:
        logger.error(f"Error in video command: {str(e)}", exc_info=True)
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"An error occurred: {str(e)}")

@bot.command(name='klingat')
async def klingat(ctx):
    """Generate a video using the new experimental back-end."""
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
    await user.send("Generating video... This may take a while.")

    try:
        # Step 1: Generate video from image using Kling with video-specific prompt (set the duration below, that will be passed to replicate manager)
        prompt = await ctx.bot.image_manager.generate_video_prompt(ctx.bot.conversation_manager.get_conversation())
        kling_video_url = await ctx.bot.replicate_manager.generate_kling_video(selfie_path, prompt, duration=10)
        
        if not kling_video_url:
            await user.send("Failed to generate initial video.")
            return

        # Step 2: Apply lip sync using LatentSync
        final_video_url = await ctx.bot.replicate_manager.apply_latentsync(kling_video_url, audio_path)
        
        if not final_video_url:
            await user.send("Failed to apply lip sync.")
            return

        # Download and save the final video
        async with aiohttp.ClientSession() as session:
            async with session.get(final_video_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, "vlog2_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    
                    await user.send(file=discord.File(video_path))
                else:
                    await user.send(f"Failed to download the generated video. Status code: {resp.status}")

    except Exception as e:
        logger.error(f"Error in klingat command: {str(e)}", exc_info=True)
        await user.send(f"An error occurred: {str(e)}")



@bot.command()
async def talker(ctx, **kwargs):
    """Generate a talking face video."""
    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send("Generating talking face video... This may take a while.")
    
    last_audio, last_selfie = ctx.bot.conversation_manager.get_last_audio_and_selfie()
    
    logger.debug(f"Last audio path: {last_audio}")
    logger.debug(f"Last selfie path: {last_selfie}")
    
    if not last_audio or not last_selfie:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Error: Missing recent audio message or selfie. Please make sure both are available in the conversation history.")
        return

    try:
        with open(last_audio, "rb") as audio_file, open(last_selfie, "rb") as image_file:
            prediction = await ctx.bot.replicate_manager.generate_talking_face(
                driven_audio=audio_file,
                source_image=image_file,
                **kwargs
            )
        
        if prediction is None:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("Error: Failed to generate the talking face. Please check the console for more details.")
            return
        
        output_url = prediction if isinstance(prediction, str) else prediction[0]
        
        logger.debug(f"Output URL: {output_url}")
        
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Downloading the generated video...")
        async with aiohttp.ClientSession() as session:
            async with session.get(output_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, "talking_face.mp4")
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    
                    user = await bot.fetch_user(ctx.bot.args.discord_id)
                    await user.send("Here's the generated talking face video:", file=discord.File(video_path))
                else:
                    user = await bot.fetch_user(ctx.bot.args.discord_id)
                    await user.send(f"Failed to download the generated video. Status code: {resp.status}")
    except Exception as e:
        logger.error(f"Error in talker command: {str(e)}", exc_info=True)
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"An error occurred: {str(e)}")

# --- NEW COMMAND START ---
@bot.command()
async def hedra(ctx):
    """Generate a video using Hedra."""
    if not ctx.bot.conversation_manager or not ctx.bot.hedra_manager:
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
    await user.send("Generating video with Hedra... This may take a while.")

    try:
        video_url, error = await ctx.bot.hedra_manager.generate_video(audio_path, selfie_path)

        if error:
            await user.send(f"Failed to generate video: {error}")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, "hedra_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    
                    await user.send(file=discord.File(video_path))
                else:
                    await user.send(f"Failed to download the generated video. Status code: {resp.status}")

    except Exception as e:
        logger.error(f"Error in hedra command: {str(e)}", exc_info=True)
        await user.send(f"An error occurred: {str(e)}")

@bot.command()
async def wan(ctx):
    """Generate a video using the WAN I2V model."""
    if not ctx.bot.conversation_manager or not ctx.bot.image_manager or not ctx.bot.replicate_manager:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("Bot is not fully initialized. Please try again later.")
        return

    # Get last selfie path
    selfie_path = ctx.bot.conversation_manager.get_last_selfie_path()
    if not selfie_path:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send("No recent selfie found. Generate one first using !pic.")
        return

    user = await bot.fetch_user(ctx.bot.args.discord_id)
    await user.send("Generating WAN video prompt...")

    try:
        # Generate the simple action prompt
        wan_prompt = await ctx.bot.image_manager.generate_wan_video_prompt(ctx.bot.conversation_manager.get_conversation())
        if not wan_prompt:
            await user.send("Failed to generate video prompt.")
            return

        await user.send(f"Generating WAN video with prompt: `{wan_prompt}`... This may take a while.")

        # Generate the video using ReplicateManager
        video_url = await ctx.bot.replicate_manager.generate_wan_video(selfie_path, wan_prompt)

        if not video_url:
            await user.send("Failed to generate WAN video.")
            return

        # Download and send the video
        await user.send("Downloading generated video...")
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    # Save the video
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_filename = f"wan_video_{timestamp}.mp4"
                    video_path = os.path.join(ctx.bot.conversation_manager.subfolder_path, video_filename)
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    logger.info(f"WAN video saved to: {video_path}")
                    # Send the video file
                    await user.send(file=discord.File(video_path))
                else:
                    logger.error(f"Failed to download WAN video. Status: {resp.status}, URL: {video_url}")
                    await user.send(f"Failed to download the generated video (Status: {resp.status}).")

    except Exception as e:
        logger.error(f"Error in !wan command: {e}", exc_info=True)
        await user.send(f"An unexpected error occurred during the !wan command: {e}")
# --- NEW COMMAND END ---

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
        # Use ctx.bot.api_manager
        current_model = ctx.bot.api_manager.get_current_model()
        available_models = ", ".join([f"{full_name} ({short_code})" for full_name, short_code in CLAUDE_MODELS.items()])
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Current Claude model: {current_model}\nAvailable models: {available_models}")
    # Use ctx.bot.api_manager
    elif ctx.bot.api_manager.switch_claude_model(model_code):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        # Use ctx.bot.api_manager
        await user.send(f"Switched to Claude model: {ctx.bot.api_manager.get_current_model()}")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Invalid Claude model code. Available models: {', '.join(CLAUDE_MODELS.values())}")

@bot.command()
async def openrouter(ctx, model_code=None):
    """Switch or view OpenRouter models."""
    if model_code is None:
        # Use ctx.bot.api_manager
        current_model = ctx.bot.api_manager.get_current_model()
        available_models = ", ".join([f"{full_name} ({short_code})" for full_name, short_code in OPENROUTER_MODELS.items()])
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Current OpenRouter model: {current_model}\nAvailable models: {available_models}")
    # Use ctx.bot.api_manager
    elif ctx.bot.api_manager.switch_openrouter_model(model_code):
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        # Use ctx.bot.api_manager
        await user.send(f"Switched to OpenRouter model: {ctx.bot.api_manager.get_current_model()}")
    else:
        user = await bot.fetch_user(ctx.bot.args.discord_id)
        await user.send(f"Invalid OpenRouter model code. Available models: {', '.join(OPENROUTER_MODELS.values())}")

@bot.command()
async def lmstudio(ctx, model_name=None):
    """Switch or view LMStudio models."""
    if model_name is None:
        # Use ctx.bot.api_manager
        models = await ctx.bot.api_manager.fetch_lmstudio_models()
        if models:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send(f"Available LMStudio models: {', '.join(models)}")
        else:
            user = await bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("No LMStudio models available or couldn't fetch the list.")
    # Use ctx.bot.api_manager
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
        # Use ctx.bot.api_manager
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
