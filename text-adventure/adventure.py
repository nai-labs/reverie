# adventure.py
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

# Add parent directory to path so we can import from parent
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import from parent directory
from users import get_user_id, list_users

# Import from local directory
from config import (
    DISCORD_BOT_TOKEN,
    COMMAND_PREFIX,
    LOG_LEVEL,
    LOG_FORMAT,
    DEFAULT_ADVENTURE_MODEL
)
from gamemasters import gamemasters
from adventure_manager import AdventureManager
from scene_manager import SceneManager
from api_manager import APIManager

# Set up logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Gamemaster validation function
def validate_gamemaster(name: str) -> bool:
    if name not in gamemasters:
        print(f"Error: Game Master '{name}' not found.")
        print(f"Available Game Masters: {', '.join(gamemasters.keys())}")
        return False
    return True

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run Text Adventure Discord bot')
    parser.add_argument('--user', required=True, help=f'Username from users.py. Available: {", ".join(list_users())}')
    parser.add_argument('--gamemaster', default="ModernLife", help='Game Master to use')
    
    # Add LLM settings arguments
    parser.add_argument('--main-provider', help='Main conversation LLM provider')
    parser.add_argument('--main-model', help='Main conversation model')
    parser.add_argument('--media-provider', help='Provider for prompt generation (e.g., OpenRouter)')
    parser.add_argument('--media-model', help='Model for prompt generation')
    parser.add_argument('--image-service', default='Stable Diffusion (Local)', help='Service for final image generation (e.g., Stable Diffusion (Local), OpenAI)')

    args = parser.parse_args()
    
    # Validate gamemaster
    if not validate_gamemaster(args.gamemaster):
        sys.exit(1)
    
    # Validate user
    try:
        args.discord_id = get_user_id(args.user)
    except ValueError as e:
        print(str(e))
        sys.exit(1)
    
    return args

# Set up Discord bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, heartbeat_timeout=60)

# Initialize global variables
api_manager = APIManager()
bot_initialized = False
adventure_manager: Optional[AdventureManager] = None
scene_manager: Optional[SceneManager] = None
args: Optional[argparse.Namespace] = None

@bot.event
async def on_ready():
    """Event handler for when the bot is ready and connected to Discord."""
    global adventure_manager, scene_manager, bot_initialized, args, api_manager
    try:
        logger.info(f'Bot is ready. Logged in as {bot.user.name} (ID: {bot.user.id})')
        
        # Get arguments and store in bot instance
        bot.args = parse_args()
        args = bot.args
        logger.info(f"Initializing bot with Game Master '{args.gamemaster}' for user '{args.user}' (ID: {args.discord_id})")
        
        # Try to fetch the user
        try:
            user = await bot.fetch_user(args.discord_id)
            logger.info(f"Successfully found user: {user.name} (ID: {user.id})")
        except discord.NotFound:
            logger.error(f"Could not find user with ID {args.discord_id}")
            await bot.close()
            return
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch user: {str(e)}")
            await bot.close()
            return

        # Initialize managers
        logger.info("Initializing managers...")
        adventure_manager = AdventureManager(args.gamemaster)
        
        # Prepare LLM settings dictionary from args, including None values if not provided
        llm_settings = {
            "main_provider": args.main_provider,
            "main_model": args.main_model,
            "media_provider": args.media_provider, # For prompt generation model selection in APIManager if needed later
            "media_model": args.media_model,     # For prompt generation model selection in APIManager if needed later
            # Note: image_service is handled by SceneManager directly
        }
        logger.info(f"Passing LLM settings from args: {llm_settings}")

        # Initialize API manager with potentially partial settings from command-line
        api_manager = APIManager(llm_settings)
        logger.info(f"API Manager initialized with main provider: {api_manager.current_llm}, main model: {api_manager.get_current_model()}")
        
        # Initialize scene manager, passing the prompt model and image service
        scene_manager = SceneManager(
            adventure_manager,
            args.gamemaster,
            media_model=args.media_model, # Pass model for prompt gen
            image_generation_service=args.image_service # Pass the selected image service
        )
        logger.info(f"Scene Manager initialized with prompt model: {scene_manager.prompt_generation_model}, image service: {getattr(scene_manager, 'image_generation_service', 'N/A')}")

        # Set up log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_name = f"adventure_{timestamp}"
        adventure_manager.set_log_file(log_file_name)
        logger.info(f"Log file set to: {adventure_manager.log_file}")

        bot_initialized = True
        logger.info("Bot initialization complete")
    
        # Send available commands
        logger.info("Sending initial message to user...")
        try:
            await user.send(f"""```Available commands:
{COMMAND_PREFIX}pic [mode] - Generate an image of the current scene
  Modes:
  - direct (default): Use italicized text directly
  - generate: Create new prompt from context
  - enhance: Enhance italicized text
{COMMAND_PREFIX}resume <path> - Resume a previous adventure
```""")
            logger.info("Initial message sent successfully")
        except discord.Forbidden:
            logger.error(f"Cannot send messages to user {user.name} (ID: {user.id})")
            await bot.close()
            return
        except Exception as e:
            logger.error(f"Failed to send initial message: {str(e)}")
            await bot.close()
            return

        # Try to send initial GM message
        try:
            logger.info(f"Generating initial response using model: {api_manager.get_current_model()}")
            response_text = await api_manager.generate_response(
                gamemasters[args.gamemaster]["scenario"],
                [],  # Empty conversation history
                adventure_manager.system_prompt
            )
            
            if response_text:
                adventure_manager.add_gm_response(response_text)
                response_chunks = adventure_manager.split_response(response_text)
                for chunk in response_chunks:
                    await user.send(chunk)
                logger.info("Initial GM message sent successfully")

                # Reverted automatic generation/reference logic from here

        except Exception as e:
            logger.error(f"Error starting adventure: {str(e)}", exc_info=True)
            await user.send("I encountered an error while starting the adventure. Please try sending a message.")
            
    except Exception as e:
        logger.error(f"Error in on_ready: {str(e)}", exc_info=True)
        await bot.close()

@bot.event
async def on_message(message):
    """Event handler for incoming messages."""
    global bot_initialized, adventure_manager, scene_manager, api_manager, args

    if message.author == bot.user:
        return

    # Process commands
    await bot.process_commands(message)

    # Ignore messages that are commands or not from the initiating user
    if message.content.startswith(bot.command_prefix) or message.author.id != bot.args.discord_id:
        return

    # Check if the bot is initialized
    if not bot_initialized:
        return

    try:
        # Process the player's action
        if message.content:
            await process_action(message, message.content)

    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}", exc_info=True)
        user = await bot.fetch_user(bot.args.discord_id)
        await user.send("I encountered an unexpected error. Please try again later.")

async def process_action(message, content):
    """Process a player's action and generate the GM's response."""
    try:
        # Log current model before generating response
        logger.info(f"Generating response using model: {api_manager.get_current_model()}")
        
        # Handle conversation and generate response
        response_text = await api_manager.generate_response(
            content,
            adventure_manager.get_conversation(),
            adventure_manager.system_prompt
        )
        
        if response_text:
            adventure_manager.add_player_action(content)
            adventure_manager.add_gm_response(response_text)

            # Send the response only to the specified user
            user = await bot.fetch_user(bot.args.discord_id)
            response_chunks = adventure_manager.split_response(response_text)
            for chunk in response_chunks:
                await user.send(chunk)

            # --- Attempt automatic image generation ---
            # Pass the player action (content) and the GM response (response_text)
            # Note: We need to define attempt_automatic_image_generation later
            await attempt_automatic_image_generation(content, response_text) # Uncommented now

        else:
            user = await bot.fetch_user(bot.args.discord_id)
            await user.send("I apologize, but I couldn't generate a response at this time.")

    except Exception as e:
        logger.error(f"Error in process_action: {str(e)}", exc_info=True)
        user = await bot.fetch_user(args.discord_id)
        await user.send("I encountered an unexpected error while processing your action. Please try again later.")


# --- Helper Functions for Image Generation ---

async def attempt_automatic_image_generation(player_action: str, gm_response_text: str):
    """Generates and sends an image automatically based on the GM response."""
    global scene_manager, adventure_manager, args
    if not scene_manager or not adventure_manager: return

    # Use 'direct' mode for automatic generation for now
    # TODO: Consider if 'generate' or 'enhance' might be better for auto mode
    mode = "direct"
    logger.info(f"Attempting automatic image generation (mode: {mode})...")

    # Generate the base prompt (e.g., the italicized text)
    scene_prompt = await scene_manager.generate_scene_prompt(adventure_manager.get_conversation(), mode)

    if scene_prompt:
        user = await bot.fetch_user(args.discord_id)
        logger.info(f"Auto-generating image with prompt: {scene_prompt}")
        # Pass context to generate_image
        image_data = await scene_manager.generate_image(
            prompt=scene_prompt,
            player_action=player_action,
            gm_outcome=gm_response_text # Pass the full GM response as outcome context
        )
        if image_data:
            image_path = await scene_manager.save_image(image_data)
            if image_path:
                adventure_manager.set_last_scene_path(image_path)
                try:
                    await user.send(file=discord.File(image_path))
                    logger.info(f"Automatically generated image sent: {image_path}")
                except Exception as e:
                    logger.error(f"Failed to send automatically generated image: {e}")
            else:
                logger.error("Failed to save automatically generated image.")
        else:
            logger.error("Failed to generate image automatically.")
    else:
        logger.warning("Could not generate prompt for automatic image generation.")

# --- Bot Commands ---

@bot.command()
async def pic(ctx, mode: str = "direct"):
    """
    Generate an image of the current scene.
    
    Modes:
    - direct: Use italicized text directly from GM's response (default)
    - generate: Generate new prompt from conversation context
    - enhance: Use italicized text as input to generate enhanced prompt
    """
    if mode not in ["direct", "generate", "enhance"]:
        user = await bot.fetch_user(args.discord_id)
        await user.send("Invalid mode. Use: direct, generate, or enhance")
        return
        
    logger.info(f"Generating image with mode: {mode}")
    prompt = await scene_manager.generate_scene_prompt(adventure_manager.get_conversation(), mode)

    # --- Get context for image generation ---
    last_player_action = adventure_manager.get_last_player_action()
    last_gm_response = adventure_manager.get_last_gm_response()
    # We might only want the *outcome* part of the GM response, not the whole thing including new prompts/choices.
    # This requires more sophisticated parsing or assumptions about GM response structure.
    # For now, pass the full last GM response.

    if prompt:
        user = await bot.fetch_user(args.discord_id)
        await user.send(f"Generating scene image in {mode} mode... This may take a moment.")
        # Pass context to generate_image
        image_data = await scene_manager.generate_image(
            prompt=prompt,
            player_action=last_player_action,
            gm_outcome=last_gm_response
        )
        if image_data:
            image_path = await scene_manager.save_image(image_data)
            adventure_manager.set_last_scene_path(image_path)
            await user.send(file=discord.File(image_path))
        else:
            await user.send("Failed to generate scene image.")
    else:
        user = await bot.fetch_user(args.discord_id)
        await user.send("Failed to generate scene description.")

@bot.command()
async def resume(ctx, directory_path):
    """Resume a previous adventure from a log file."""
    success = adventure_manager.resume_adventure(directory_path)
    if success:
        user = await bot.fetch_user(args.discord_id)
        await user.send(f"Resumed adventure from: {adventure_manager.log_file}")
        
        # Send the last GM response to refresh the current scene
        last_message = adventure_manager.get_last_message()
        if last_message:
            await user.send("Current scene:")
            response_chunks = adventure_manager.split_response(last_message)
            for chunk in response_chunks:
                await user.send(chunk)
    else:
        user = await bot.fetch_user(args.discord_id)
        await user.send("Failed to resume adventure. Please check the directory path.")

if __name__ == "__main__":
    logger.info("Starting adventure.py")
    try:
        # Verify bot token
        if not DISCORD_BOT_TOKEN:
            logger.error("DISCORD_BOT_TOKEN is not set in environment variables")
            sys.exit(1)
        if len(DISCORD_BOT_TOKEN) < 50:  # Discord tokens are typically longer
            logger.error("DISCORD_BOT_TOKEN appears to be invalid (too short)")
            sys.exit(1)
            
        logger.info("Starting Discord bot...")
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
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
