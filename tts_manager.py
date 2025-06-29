# tts_manager.py
import os
import re
import aiohttp  
from datetime import datetime
import logging
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_SETTINGS
from characters import characters
import discord 

logger = logging.getLogger(__name__)

class TTSManager:
    def __init__(self, character_name, conversation_manager):
        self.character_name = character_name
        self.conversation_manager = conversation_manager
        character_config = characters[character_name]
        self.current_voice_id = character_config.get("tts_url", "").split("/")[-1]
        self.voice_settings = character_config.get("voice_settings", ELEVENLABS_VOICE_SETTINGS)
        self.include_narration = False
        logger.info(f"TTSManager initialized for character: {character_name}")
        logger.info(f"Current voice ID: {self.current_voice_id}")

    def toggle_narration(self):
        self.include_narration = not self.include_narration
        logger.info(f"Narration toggled: {self.include_narration}")

    def get_tts_text(self, message):
        if self.include_narration:
            return message
        else:
            return re.sub(r'\*.*?\*', '', message)

    def set_voice_id(self, voice_id):
        self.current_voice_id = voice_id
        logger.info(f"Voice ID set to: {voice_id}")
        return True

    def get_current_voice_id(self):
        return self.current_voice_id

    async def send_tts(self, bot, text):
        user = await bot.fetch_user(bot.args.discord_id)
        tts_text = self.get_tts_text(text)
        audio_path = await self.generate_tts_file(tts_text)
        if audio_path:
            await user.send(f"Generated TTS file: {os.path.basename(audio_path)}", file=discord.File(audio_path))
            self.conversation_manager.set_last_audio_path(audio_path)
        else:
            logger.error("Failed to generate TTS file")
            await user.send("Failed to generate TTS.")

    async def send_tts_file(self, ctx, text):
        user = await ctx.bot.fetch_user(ctx.bot.args.discord_id)
        tts_text = self.get_tts_text(text)
        audio_path = await self.generate_tts_file(tts_text)
        if audio_path:
            await user.send(f"Generated TTS file: {os.path.basename(audio_path)}", file=discord.File(audio_path))
            self.conversation_manager.set_last_audio_path(audio_path)
        else:
            logger.error("Failed to generate TTS file")
            await user.send("Failed to generate TTS.")

    async def generate_tts_file(self, text):
        if not ELEVENLABS_API_KEY:
            logger.error("ElevenLabs API key is not set")
            return None

        headers = {
            'Content-Type': 'application/json',
            'xi-api-key': ELEVENLABS_API_KEY,
        }

        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": self.voice_settings
        }

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.current_voice_id}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        tts_file_name = f"tts_response_{timestamp}.mp3"
                        tts_file_path = os.path.join(self.conversation_manager.subfolder_path, tts_file_name)
                        with open(tts_file_path, 'wb') as f:
                            f.write(audio_data)
                        logger.info(f"TTS file generated successfully: {tts_file_path}")
                        return tts_file_path
                    else:
                        error_content = await response.text()
                        logger.error(f"Error generating TTS: Status {response.status}, Content: {error_content}")
                        return None
        except Exception as e:
            logger.exception(f"Exception occurred while generating TTS: {str(e)}")
            return None
