# main.py
import asyncio
import discord
from discord.ext import commands
import aiohttp
import os
import logging
from typing import Optional
from datetime import datetime

from config import (
    DISCORD_BOT_TOKEN,
    DISCORD_USER_ID,
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
from characters import characters

# Set up logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Set up Discord bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, heartbeat_timeout=60)

# Initialize global variables
api_manager = APIManager()
bot_initialized = False
conversation_manager: Optional[ConversationManager] = None
tts_manager: Optional[TTSManager] = None
image_manager: Optional[ImageManager] = None
replicate_manager: Optional[ReplicateManager] = None

@bot.event
async def on_ready():
    """Event handler for when the bot is ready and connected to Discord."""
    global conversation_manager, tts_manager, image_manager, replicate_manager, bot_initialized
    logger.info(f'Bot is ready. Logged in as {bot.user.name}')
    user = await bot.fetch_user(DISCORD_USER_ID)
    await user.send(f"```Type {COMMAND_PREFIX}help for a list of available commands.```")

    # Initialize managers with Layla as the character
    conversation_manager = ConversationManager("Layla")
    tts_manager = TTSManager("Layla", conversation_manager)
    image_manager = ImageManager(conversation_manager, "Layla")
    replicate_manager = ReplicateManager()

    # Set up log file
    log_file_name = f"layla_conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    conversation_manager.set_log_file(log_file_name)
    await user.send(f"```Log file set to: {conversation_manager.log_file}```")

    bot_initialized = True

    # Send available commands
    await user.send(f"""```Available commands:
{COMMAND_PREFIX}delete - Delete the last message
{COMMAND_PREFIX}edit <new_content> - Edit the last message
{COMMAND_PREFIX}narration - Toggle narration
{COMMAND_PREFIX}tts - Toggle TTS
{COMMAND_PREFIX}llm - Switch LLM
{COMMAND_PREFIX}claude_model [model_name] - Switch or view Claude models
{COMMAND_PREFIX}say - Generate TTS for the last message or a specified text
{COMMAND_PREFIX}resume <directory_path> - Resume conversation from a log file
{COMMAND_PREFIX}selfie - Generate a selfie image
{COMMAND_PREFIX}talker - Generate a talking face video
{COMMAND_PREFIX}set_expression <value> - Set expression scale
{COMMAND_PREFIX}set_pose <value> - Set pose style
{COMMAND_PREFIX}restart - Restart the bot
{COMMAND_PREFIX}quit - Stop the bot```""")

@bot.event
async def on_message(message):
    """Event handler for incoming messages."""
    global bot_initialized, conversation_manager, tts_manager, api_manager

    if message.author == bot.user:
        return

    # Process commands
    await bot.process_commands(message)

    # Ignore messages that are commands or not from the initiating user
    if message.content.startswith(bot.command_prefix) or message.author.id != DISCORD_USER_ID:
        return

    # Check if the bot is initialized
    if not bot_initialized:
        return

    try:
        # Check for text file attachments
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.endswith('.txt'):
                    file_content = await attachment.read()
                    text_content = file_content.decode('utf-8')
                    await process_message(message, text_content)
                    return  # Exit after processing the first text file

        # If no text file attachment, process the message content as usual
        if message.content:
            await process_message(message, message.content)

    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}", exc_info=True)
        await message.channel.send("I encountered an unexpected error. Please try again later.")

async def process_message(message, content):
    """Process a message and generate a response."""
    try:
        # Add day of the week and time to the user's message
        current_time = datetime.now()
        day_of_week = current_time.strftime("%A")
        time = current_time.strftime("%I:%M %p")
        content_with_time = f"{content}\n\nCurrent day: {day_of_week}\nCurrent time: {time}"

        # Handle conversation and generate response
        response_text = await api_manager.generate_response(content_with_time, conversation_manager.get_conversation(), conversation_manager.system_prompt)
        
        if response_text:
            conversation_manager.add_user_message(content)
            conversation_manager.add_assistant_response(response_text)

            # Send the response
            response_chunks = conversation_manager.split_response(response_text)
            for chunk in response_chunks:
                await message.channel.send(chunk)

            # Generate and send TTS
            await tts_manager.send_tts(message.channel, response_text)
        else:
            await message.channel.send("I apologize, but I couldn't generate a response at this time.")
    
    except Exception as e:
        logger.error(f"Error in process_message: {str(e)}", exc_info=True)
        await message.channel.send("I encountered an unexpected error while processing your message. Please try again later.")

# Conversation Management Commands

@bot.command()
async def delete(ctx):
    """Delete the last message in the conversation."""
    deleted_message = conversation_manager.delete_last_message()
    if deleted_message:
        await ctx.send("Last message deleted from the conversation.")
        last_message = conversation_manager.get_last_message()
        if last_message:
            first_three_words = ' '.join(last_message.split()[:3])
            await ctx.send(f"The new last message starts with: ```{first_three_words}...```")
        else:
            await ctx.send("The conversation history is now empty.")
    else:
        await ctx.send("No messages to delete.")

@bot.command()
async def edit(ctx, *, new_content):
    """Edit the last message in the conversation."""
    edited_message = conversation_manager.edit_last_message(new_content)
    if edited_message:
        await ctx.send("Last message edited in the conversation.")
        last_message = conversation_manager.get_last_message()
        first_three_words = ' '.join(last_message.split()[:3])
        await ctx.send(f"The edited message starts with: ```{first_three_words}...```")
    else:
        await ctx.send("No messages to edit.")

@bot.command()
async def resume(ctx, directory_path):
    """Resume a conversation from a log file."""
    success = conversation_manager.resume_conversation(directory_path)
    if success:
        await ctx.send(f"Resumed conversation from: {conversation_manager.log_file}")
    else:
        await ctx.send("Failed to resume conversation. Please check the directory path.")

# TTS Commands

@bot.command()
async def narration(ctx):
    """Toggle narration in TTS."""
    tts_manager.toggle_narration()
    if tts_manager.include_narration:
        await ctx.send("```Narration text will be included in the audio.```")
    else:
        await ctx.send("```Narration text will be excluded from the audio.```")

@bot.command()
async def tts(ctx):
    """Toggle TTS functionality."""
    tts_manager.toggle_tts()
    if tts_manager.tts_enabled:
        await ctx.send("```TTS functionality is now enabled using ElevenLabs API.```")
    else:
        await ctx.send("```TTS functionality is now disabled.```")

@bot.command()
async def say(ctx):
    """Generate TTS for the last message or specified text."""
    command_text = ctx.message.content[len(f'{COMMAND_PREFIX}say'):].strip()
    if command_text:
        tts_text = command_text
    else:
        last_message = conversation_manager.get_last_message()
        if last_message:
            tts_text = tts_manager.get_tts_text(last_message)
        else:
            await ctx.send("No preceding message found in the conversation.")
            return

    # Generate the audio file regardless of TTS being enabled
    audio_file = await tts_manager.generate_tts_audio_always(tts_text)
    
    if audio_file:
        await ctx.send(file=discord.File(audio_file, filename="tts_audio.mp3"))
    else:
        await ctx.send("Failed to generate TTS audio.")

@bot.command()
async def set_voice(ctx, voice_id):
    """Set the voice ID for TTS."""
    if tts_manager.set_voice_id(voice_id):
        await ctx.send(f"Voice ID set to: {voice_id}")
    else:
        await ctx.send("Failed to set voice ID.")

@bot.command()
async def get_voice(ctx):
    """Get the current voice ID for TTS."""
    current_voice_id = tts_manager.get_current_voice_id()
    await ctx.send(f"Current voice ID: {current_voice_id}")

# Image and Video Commands

@bot.command()
async def selfie(ctx):
    """Generate a selfie image."""
    prompt = await image_manager.generate_selfie_prompt(conversation_manager.get_conversation())
    image_data = await image_manager.generate_image(prompt)
    if image_data:
        image_path = await image_manager.save_image(image_data)
        conversation_manager.set_last_selfie_path(image_path)
        await ctx.send(file=discord.File(image_path))
        await ctx.author.send(f"```{prompt}```")
    else:
        await ctx.send("Failed to generate selfie image.")

@bot.command()
async def video(ctx):
    """Generate a video using the last audio and character's input video."""
    if not conversation_manager or not replicate_manager:
        await ctx.send("Bot is not fully initialized. Please try again later.")
        return

    await ctx.send("Generating video... This may take a while.")

    face_path = characters[conversation_manager.character_name].get("input_video")
    if not face_path or not os.path.exists(face_path):
        await ctx.send(f"Input video not found at path: {face_path}")
        return

    audio_path = conversation_manager.get_last_audio_file()
    if not audio_path:
        await ctx.send("No recent audio file found.")
        return

    try:
        output = await asyncio.create_task(replicate_manager.generate_video_retalking(face_path, audio_path))

        if output is None:
            await ctx.send("Failed to generate the video. Please check the logs for more details.")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(output) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    video_path = os.path.join(conversation_manager.subfolder_path, "retalking_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    
                    await ctx.send("Here's the generated video:", file=discord.File(video_path))
                else:
                    await ctx.send(f"Failed to download the generated video. Status code: {resp.status}")
    except Exception as e:
        logger.error(f"Error in video command: {str(e)}", exc_info=True)
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command()
async def talker(ctx, **kwargs):
    """Generate a talking face video."""
    await ctx.send("Generating talking face video... This may take a while.")
    
    last_audio, last_selfie = conversation_manager.get_last_audio_and_selfie()
    
    logger.debug(f"Last audio path: {last_audio}")
    logger.debug(f"Last selfie path: {last_selfie}")
    
    if not last_audio or not last_selfie:
        await ctx.send("Error: Missing recent audio message or selfie. Please make sure both are available in the conversation history.")
        return

    try:
        with open(last_audio, "rb") as audio_file, open(last_selfie, "rb") as image_file:
            prediction = await replicate_manager.generate_talking_face(
                driven_audio=audio_file,
                source_image=image_file,
                **kwargs
            )
        
        if prediction is None:
            await ctx.send("Error: Failed to generate the talking face. Please check the console for more details.")
            return
        
        output_url = prediction if isinstance(prediction, str) else prediction[0]
        
        logger.debug(f"Output URL: {output_url}")
        
        await ctx.send("Downloading the generated video...")
        async with aiohttp.ClientSession() as session:
            async with session.get(output_url) as resp:
                if resp.status == 200:
                    video_data = await resp.read()
                    video_path = os.path.join(conversation_manager.subfolder_path, "talking_face.mp4")
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    
                    await ctx.send("Here's the generated talking face video:", file=discord.File(video_path))
                else:
                    await ctx.send(f"Failed to download the generated video. Status code: {resp.status}")
    except Exception as e:
        logger.error(f"Error in talker command: {str(e)}", exc_info=True)
        await ctx.send(f"An error occurred: {str(e)}")

# Replicate Manager Commands

@bot.command()
async def set_expression(ctx, value: float):
    """Set the expression scale for the talking face generation."""
    result = replicate_manager.set_expression_scale(value)
    await ctx.send(result)

@bot.command()
async def set_pose(ctx, value: int):
    """Set the pose style for the talking face generation."""
    result = replicate_manager.set_pose_style(value)
    await ctx.send(result)

@bot.command()
async def set_facerender(ctx, value: str):
    """Set the face render method for the talking face generation."""
    result = replicate_manager.set_facerender(value)
    await ctx.send(result)

@bot.command()
async def set_preprocess(ctx, value: str):
    """Set the preprocess method for the talking face generation."""
    result = replicate_manager.set_preprocess(value)
    await ctx.send(result)

@bot.command()
async def set_still_mode(ctx, value: str):
    """Set the still mode for the talking face generation."""
    result = replicate_manager.set_still_mode(value)
    await ctx.send(result)

@bot.command()
async def set_use_enhancer(ctx, value: str):
    """Set whether to use enhancer for the talking face generation."""
    result = replicate_manager.set_use_enhancer(value)
    await ctx.send(result)

@bot.command()
async def set_use_eyeblink(ctx, value: str):
    """Set whether to use eye blink for the talking face generation."""
    result = replicate_manager.set_use_eyeblink(value)
    await ctx.send(result)

@bot.command()
async def set_size_of_image(ctx, value: int):
    """Set the size of the image for the talking face generation."""
    result = replicate_manager.set_size_of_image(value)
    await ctx.send(result)

# LLM and Model Commands

@bot.command()
async def claude(ctx, model_code=None):
    """Switch or view Claude models."""
    if model_code is None:
        current_model = api_manager.get_current_model()
        available_models = ", ".join([f"{full_name} ({short_code})" for full_name, short_code in CLAUDE_MODELS.items()])
        await ctx.send(f"Current Claude model: {current_model}\nAvailable models: {available_models}")
    elif api_manager.switch_claude_model(model_code):
        await ctx.send(f"Switched to Claude model: {api_manager.get_current_model()}")
    else:
        await ctx.send(f"Invalid Claude model code. Available models: {', '.join(CLAUDE_MODELS.values())}")

@bot.command()
async def openrouter(ctx, model_code=None):
    """Switch or view OpenRouter models."""
    if model_code is None:
        current_model = api_manager.get_current_model()
        available_models = ", ".join([f"{full_name} ({short_code})" for full_name, short_code in OPENROUTER_MODELS.items()])
        await ctx.send(f"Current OpenRouter model: {current_model}\nAvailable models: {available_models}")
    elif api_manager.switch_openrouter_model(model_code):
        await ctx.send(f"Switched to OpenRouter model: {api_manager.get_current_model()}")
    else:
        await ctx.send(f"Invalid OpenRouter model code. Available models: {', '.join(OPENROUTER_MODELS.values())}")

@bot.command()
async def lmstudio(ctx, model_name=None):
    """Switch or view LMStudio models."""
    if model_name is None:
        models = await api_manager.fetch_lmstudio_models()
        if models:
            await ctx.send(f"Available LMStudio models: {', '.join(models)}")
        else:
            await ctx.send("No LMStudio models available or couldn't fetch the list.")
    elif api_manager.set_lmstudio_model(model_name):
        await ctx.send(f"Switched to LMStudio model: {model_name}")
    else:
        await ctx.send(f"Failed to switch to LMStudio model: {model_name}")

@bot.command()
async def llm(ctx, llm_name=None):
    """Switch or view current LLM and model."""
    if llm_name is None:
        current_llm = api_manager.get_current_llm()
        current_model = api_manager.get_current_model()
        available_llms = "anthropic, openrouter, lmstudio"
        
        response = f"Current LLM: {current_llm}\n"
        response += f"Current Model: {current_model}\n\n"
        response += f"Available LLMs: {available_llms}\n"
        response += f"Use '{COMMAND_PREFIX}llm <llm_name>' to switch LLMs.\n"
        response += f"Use '{COMMAND_PREFIX}claude', '{COMMAND_PREFIX}openrouter', or '{COMMAND_PREFIX}lmstudio' to see or switch specific models."
        
        await ctx.send(f"```{response}```")
    elif api_manager.switch_llm(llm_name):
        new_model = api_manager.get_current_model()
        await ctx.send(f"Switched to LLM: {llm_name}\nCurrent model: {new_model}")
    else:
        await ctx.send(f"Invalid LLM name. Available options: anthropic, openrouter, lmstudio")

# Bot Management Commands

@bot.command()
async def restart(ctx):
    """Restart the bot."""
    await ctx.send("Restarting bot...")
    logger.debug("Bot is restarting with code 42")
    os._exit(42)

@bot.command()
async def quit(ctx):
    """Stop the bot."""
    await ctx.send("Stopping the bot...")
    logger.debug("Quit command initiated. Force exiting with code 0.")
    os._exit(0)

if __name__ == "__main__":
    logger.info("Starting main.py")
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except SystemExit as e:
        logger.debug(f"Bot is exiting with code {e.code}")
        os._exit(e.code)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        os._exit(1)
