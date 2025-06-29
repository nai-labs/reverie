import os
from datetime import datetime
import discord
from gradio_client import Client
import logging
from config import ZONOS_URL

logger = logging.getLogger(__name__)

class ZonosManager:
    def __init__(self, character_name, conversation_manager):
        self.character_name = character_name
        self.conversation_manager = conversation_manager
        
        # Initialize Zonos client
        logger.info(f"Initializing Zonos client with URL: {ZONOS_URL}")
        try:
            self.client = Client(ZONOS_URL)
            logger.info("Successfully connected to Zonos server")
        except Exception as e:
            logger.error(f"Failed to connect to Zonos server: {str(e)}")
            raise
        
        # Default settings
        logger.info("Setting up default Zonos settings")
        self.settings = {
            "model_choice": "Zyphra/Zonos-v0.1-transformer",  # Default model
            "language": "en-us",
            "vq_single": 0.78,      # High quality
            "pitch_std": 45,        # Normal variation
            "speaking_rate": 15,    # Normal speed
            "e1": 0.0,  # Happiness
            "e2": 0.0,  # Sadness
            "e3": 0.0,  # Disgust
            "e4": 0.0,  # Fear
            "e5": 0.0,  # Surprise
            "e6": 0.0,  # Anger
            "e7": 0.0,  # Other
            "e8": 1.0,  # Neutral
            "speaker_noised": True,
            "fmax": 24000
        }
        
        # Try to load character-specific settings
        from characters import characters
        if character_name in characters and "zonos_settings" in characters[character_name]:
            logger.info(f"Loading Zonos settings for character: {character_name}")
            self.settings.update(characters[character_name]["zonos_settings"])
            
            # Load speaker audio if provided
            if "speaker_audio" in characters[character_name]["zonos_settings"]:
                self.speaker_audio = characters[character_name]["zonos_settings"]["speaker_audio"]
                logger.info(f"Using speaker audio: {self.speaker_audio}")
            else:
                logger.info("No speaker audio configured")
                self.speaker_audio = None
        else:
            logger.info(f"No Zonos settings found for character: {character_name}")
            self.speaker_audio = None

    def get_tts_text(self, message):
        """Extract text for TTS, removing any narration in asterisks"""
        # Remove text between asterisks (narration)
        import re
        return re.sub(r'\*.*?\*', '', message).strip()

    async def generate_tts_file(self, text):
        """Generate TTS audio file using Zonos"""
        logger.info(f"Generating TTS for text: {text}")
        try:
            # Create timestamp for unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"zonos_response_{timestamp}.wav"
            # Check conversation manager state
            logger.debug(f"Conversation manager state:")
            logger.debug(f"- Has subfolder_path: {hasattr(self.conversation_manager, 'subfolder_path')}")
            logger.debug(f"- Subfolder path: {getattr(self.conversation_manager, 'subfolder_path', 'Not set')}")
            logger.debug(f"- Output folder: {getattr(self.conversation_manager, 'output_folder', 'Not set')}")
            logger.debug(f"- Log file: {getattr(self.conversation_manager, 'log_file', 'Not set')}")

            # Create output folder if it doesn't exist
            if not os.path.exists(self.conversation_manager.output_folder):
                logger.debug("Creating output folder")
                os.makedirs(self.conversation_manager.output_folder)

            # Create subfolder if needed
            if not self.conversation_manager.subfolder_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.conversation_manager.set_log_file(f"session_{timestamp}")
                logger.debug(f"Created new subfolder: {self.conversation_manager.subfolder_path}")

            output_path = os.path.join(self.conversation_manager.subfolder_path, output_filename)
            logger.debug(f"Final output path will be: {output_path}")

            try:
                # Prepare speaker audio
                speaker_audio_file = None
                if self.speaker_audio and os.path.exists(self.speaker_audio):
                    with open(self.speaker_audio, 'rb') as f:
                        speaker_audio_file = f.read()
                    logger.debug(f"Using speaker audio file: {self.speaker_audio}")

                # Add debug logging
                logger.debug("Sending to Zonos API with parameters:")
                logger.debug(f"text: {text}")
                logger.debug(f"language: {self.settings['language']}")
                logger.debug(f"speaker_audio: {'Present' if speaker_audio_file else 'None'}")
                logger.debug(f"emotions: {[self.settings[f'e{i}'] for i in range(1,9)]}")
                logger.debug(f"vq_single: {self.settings['vq_single']}")
                logger.debug(f"fmax: {self.settings['fmax']}")
                logger.debug(f"pitch_std: {self.settings['pitch_std']}")
                logger.debug(f"speaking_rate: {self.settings['speaking_rate']}")

                # Generate audio using the exact API parameter order
                result = self.client.predict(
                    self.settings["model_choice"],  # model choice
                    text,                           # text to synthesize
                    self.settings["language"],      # language code
                    speaker_audio_file,             # speaker audio for cloning
                    None,                           # prefix audio (optional)
                    self.settings["e1"],           # happiness
                    self.settings["e2"],           # sadness
                    self.settings["e3"],           # disgust
                    self.settings["e4"],           # fear
                    self.settings["e5"],           # surprise
                    self.settings["e6"],           # anger
                    self.settings["e7"],           # other
                    self.settings["e8"],           # neutral
                    self.settings["vq_single"],    # VQ score
                    self.settings["fmax"],         # max frequency
                    self.settings["pitch_std"],    # pitch variation
                    self.settings["speaking_rate"], # speaking rate
                    4.0,                           # DNSMOS overall
                    self.settings["speaker_noised"],# denoise speaker
                    2.0,                           # CFG scale
                    0.15,                          # min p
                    None,                          # seed
                    True,                          # randomize seed
                    ["emotion"],                   # unconditional keys
                    api_name="/generate_audio"
                )
                logger.debug("Successfully generated audio with Zonos")
            except Exception as e:
                logger.error(f"Error in Zonos predict: {str(e)}", exc_info=True)
                logger.error(f"Exception type: {type(e)}")
                raise

            # Result is a tuple of (audio_path, seed)
            if result and len(result) > 0 and result[0]:
                if os.path.exists(result[0]):
                    import shutil
                    shutil.copy2(result[0], output_path)
                    logger.debug(f"Copied audio file to {output_path}")
                    return output_path
                else:
                    logger.error(f"Generated audio file not found at {result[0]}")
                    return None
            else:
                logger.error("No result returned from Zonos")
                return None

        except Exception as e:
            logger.error(f"Error generating TTS with Zonos: {str(e)}")
            return None

    async def send_tts_file(self, ctx, text):
        """Generate and send TTS audio file"""
        tts_text = self.get_tts_text(text)
        audio_path = await self.generate_tts_file(tts_text)
        
        if audio_path and os.path.exists(audio_path):
            # Get the user from the bot's stored args
            user = await ctx.bot.fetch_user(ctx.bot.args.discord_id)
            
            # Send the file
            await user.send(f"Generated Zonos TTS file: {os.path.basename(audio_path)}", 
                          file=discord.File(audio_path))
            
            # Store the audio path in conversation manager
            self.conversation_manager.set_last_audio_path(audio_path)
        else:
            user = await ctx.bot.fetch_user(ctx.bot.args.discord_id)
            await user.send("Failed to generate TTS with Zonos.")
