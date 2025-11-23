# conversation_manager.py
import os
import re
from datetime import datetime
from characters import characters
from database_manager import DatabaseManager

class ConversationManager:
    def __init__(self, character_name):
        self.character_name = character_name
        self.system_prompt = characters[character_name]["system_prompt"]
        self.conversation = []
        self.db = DatabaseManager()
        self.session_id = None
        self.log_file = "" # Keep for backward compatibility/path generation
        self.subfolder_path = ""
        self.log_file_name_response = None
        self.last_audio_path = None
        self.last_selfie_path = None
        self.output_folder = os.path.join(os.getcwd(), 'output')
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    def add_user_message(self, message):
        if message != self.log_file_name_response:
            self.conversation.append({"role": "user", "content": message})
            if self.session_id:
                self.db.add_message(self.session_id, "user", message)
            self.save_message_to_log("User", message)

    def add_assistant_response(self, response):
        self.conversation.append({"role": "assistant", "content": response})
        if self.session_id:
            self.db.add_message(self.session_id, "assistant", response)
        self.save_message_to_log("Bot", response)

    def add_system_message(self, message):
        """Add a system message to provide additional context."""
        self.conversation.append({"role": "system", "content": message})
        if self.session_id:
            self.db.add_message(self.session_id, "system", message)
        self.save_message_to_log("System", message)

    def delete_last_message(self):
        if len(self.conversation) > 1:
            msg = self.conversation.pop()
            if self.session_id:
                self.db.delete_last_message(self.session_id)
            return msg
        return None

    def edit_last_message(self, new_content):
        if len(self.conversation) > 1:
            self.conversation[-1]["content"] = new_content
            if self.session_id:
                self.db.edit_last_message(self.session_id, new_content)
            return self.conversation[-1]
        return None

    def get_conversation(self):
        return self.conversation

    def get_last_message(self):
        if len(self.conversation) > 0:
            return self.conversation[-1]["content"]
        return None

    def split_response(self, response, chunk_size=2000):
        return [response[i:i+chunk_size] for i in range(0, len(response), chunk_size)]

    def set_log_file(self, log_file_name):
        if not log_file_name:
            log_file_name = "latest_session"
        
        subfolder_name = log_file_name
        self.subfolder_path = os.path.join(self.output_folder, subfolder_name)
        counter = 1
        while os.path.exists(self.subfolder_path):
            subfolder_name = f"{log_file_name}_{counter}"
            self.subfolder_path = os.path.join(self.output_folder, subfolder_name)
            counter += 1
        os.makedirs(self.subfolder_path)
        
        self.log_file = os.path.join(self.subfolder_path, f"{log_file_name}.txt")
        self.session_id = log_file_name # Use log file name as session ID
        self.log_file_name_response = None

    def save_message_to_log(self, role, message):
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as file:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                file.write(f"[{timestamp}] **{role}**: {message}\n")

    def resume_conversation(self, directory_path):
        full_directory_path = os.path.join(self.output_folder, directory_path)
        if os.path.exists(full_directory_path):
            log_files = [f for f in os.listdir(full_directory_path) if f.endswith(".txt")]
            if log_files:
                log_file_path = os.path.join(full_directory_path, log_files[0])
                with open(log_file_path, 'r', encoding='utf-8') as file:
                    log_content = file.read()

                conversation_pattern = re.compile(r'\*\*User\*\*: (.*?)\n.*?\*\*Bot\*\*: (.*?)\n', re.DOTALL)
                matches = conversation_pattern.findall(log_content)

                self.conversation = []
                for user_msg, bot_msg in matches:
                    self.conversation.append({"role": "user", "content": user_msg})
                    self.conversation.append({"role": "assistant", "content": bot_msg})

                self.subfolder_path = full_directory_path
                self.log_file = log_file_path

                return True
        return False

    def save_conversation(self):
        if self.log_file:
            with open(self.log_file, 'w', encoding='utf-8') as file:
                for message in self.conversation:
                    role = message["role"].capitalize()
                    content = message["content"]
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    file.write(f"[{timestamp}] **{role}**: {content}\n")

    def set_last_audio_path(self, audio_path):
        self.last_audio_path = audio_path
        if self.session_id:
             # We might want to associate media with the last message, but for now just log it or add a system note?
             # The DB schema has media_path, let's update the last message if it was the bot?
             # Or just insert a new record for media?
             # For simplicity, let's just log it as a system event in DB or attach to last bot message?
             # Let's attach to the last message if possible, or just ignore for now as the requirement was "store messages".
             # Actually, let's add a specific method in DB or just update the last message's media_path.
             # But the schema has media_path. Let's assume we want to attach it to the last assistant message.
             pass 
        self.save_message_to_log("Bot", f"Generated audio: {os.path.basename(audio_path)}")

    def get_last_audio_file(self):
        audio_files = [f for f in os.listdir(self.subfolder_path) if f.endswith('.mp3')]
        if audio_files:
            return os.path.join(self.subfolder_path, max(audio_files, key=lambda x: os.path.getctime(os.path.join(self.subfolder_path, x))))
        return None

    def set_last_selfie_path(self, image_path):
        self.last_selfie_path = image_path
        if self.session_id:
            # Similar to audio, we could update the DB.
            pass
        self.save_message_to_log("Bot", f"Generated selfie: {os.path.basename(image_path)}")

    def get_last_selfie_path(self):
        """Get the path of the most recent selfie image."""
        image_files = [f for f in os.listdir(self.subfolder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if image_files:
            return os.path.join(self.subfolder_path, max(image_files, key=lambda x: os.path.getctime(os.path.join(self.subfolder_path, x))))
        return None

    def get_last_audio_and_selfie(self):
        return self.last_audio_path, self.last_selfie_path
