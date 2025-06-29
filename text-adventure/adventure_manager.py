# adventure_manager.py
import os
import re
from datetime import datetime
from gamemasters import gamemasters

class AdventureManager:
    def __init__(self, gamemaster_name):
        self.gamemaster_name = gamemaster_name
        self.system_prompt = gamemasters[gamemaster_name]["system_prompt"]
        self.conversation = []
        self.log_file = ""
        self.subfolder_path = ""
        self.log_file_name_response = None
        self.last_scene_path = None
        self.output_folder = os.path.join(os.getcwd(), 'output')
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    def add_player_action(self, action):
        """Add a player's action to the conversation history."""
        if action != self.log_file_name_response:
            self.conversation.append({"role": "user", "content": action})
            self.save_message_to_log("Player", action)

    def add_gm_response(self, response):
        """Add a GM's response to the conversation history."""
        self.conversation.append({"role": "assistant", "content": response})
        self.save_message_to_log("GM", response)

    def add_system_message(self, message):
        """Add a system message to provide additional context or game state information."""
        self.conversation.append({"role": "system", "content": message})
        self.save_message_to_log("System", message)

    def get_conversation(self):
        """Get the full conversation history."""
        return self.conversation

    def get_last_message(self):
        """Get the last message in the conversation."""
        if len(self.conversation) > 0:
            return self.conversation[-1]["content"]
        return None

    def split_response(self, response, chunk_size=2000):
        """Split long responses into Discord-friendly chunks."""
        return [response[i:i+chunk_size] for i in range(0, len(response), chunk_size)]

    def set_log_file(self, log_file_name):
        """Set up logging for the current adventure session."""
        if not log_file_name:
            log_file_name = "latest_adventure"
        
        subfolder_name = log_file_name
        self.subfolder_path = os.path.join(self.output_folder, subfolder_name)
        counter = 1
        while os.path.exists(self.subfolder_path):
            subfolder_name = f"{log_file_name}_{counter}"
            self.subfolder_path = os.path.join(self.output_folder, subfolder_name)
            counter += 1
        os.makedirs(self.subfolder_path)
        
        self.log_file = os.path.join(self.subfolder_path, f"{log_file_name}.txt")
        self.log_file_name_response = None

    def save_message_to_log(self, role, message):
        """Save a message to the adventure log file."""
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as file:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                file.write(f"[{timestamp}] **{role}**: {message}\n")

    def resume_adventure(self, directory_path):
        """Resume a previous adventure from a log file."""
        full_directory_path = os.path.join(self.output_folder, directory_path)
        if os.path.exists(full_directory_path):
            log_files = [f for f in os.listdir(full_directory_path) if f.endswith(".txt")]
            if log_files:
                log_file_path = os.path.join(full_directory_path, log_files[0])
                with open(log_file_path, 'r', encoding='utf-8') as file:
                    log_content = file.read()

                conversation_pattern = re.compile(r'\*\*Player\*\*: (.*?)\n.*?\*\*GM\*\*: (.*?)\n', re.DOTALL)
                matches = conversation_pattern.findall(log_content)

                self.conversation = []
                for player_msg, gm_msg in matches:
                    self.conversation.append({"role": "user", "content": player_msg})
                    self.conversation.append({"role": "assistant", "content": gm_msg})

                self.subfolder_path = full_directory_path
                self.log_file = log_file_path

                return True
        return False

    def save_adventure(self):
        """Save the current adventure state to the log file."""
        if self.log_file:
            with open(self.log_file, 'w', encoding='utf-8') as file:
                for message in self.conversation:
                    role = "Player" if message["role"] == "user" else "GM" if message["role"] == "assistant" else "System"
                    content = message["content"]
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    file.write(f"[{timestamp}] **{role}**: {content}\n")

    def set_last_scene_path(self, image_path):
        """Set the path of the last generated scene image."""
        self.last_scene_path = image_path
        self.save_message_to_log("System", f"Generated scene image: {os.path.basename(image_path)}")

    def get_last_scene_path(self):
        """Get the path of the most recent scene image."""
        image_files = [f for f in os.listdir(self.subfolder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if image_files:
            return os.path.join(self.subfolder_path, max(image_files, key=lambda x: os.path.getctime(os.path.join(self.subfolder_path, x))))
        return None
