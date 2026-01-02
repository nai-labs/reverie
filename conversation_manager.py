import os
import re
import json
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
        self.last_video_path = None
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
        
        self.log_file = os.path.join(self.subfolder_path, f"{subfolder_name}.txt")
        self.session_id = subfolder_name  # Use actual folder name as session ID
        self.log_file_name_response = None
        
        # Create session metadata
        self.save_metadata()

    def save_message_to_log(self, role, message):
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as file:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                file.write(f"[{timestamp}] **{role}**: {message}\n")

    def resume_conversation(self, directory_path):
        """Resume a conversation from an existing session folder."""
        full_directory_path = os.path.join(self.output_folder, directory_path)
        if os.path.exists(full_directory_path):
            # Find log file (exclude status.txt and metadata)
            log_files = [f for f in os.listdir(full_directory_path) 
                        if f.endswith(".txt") and f != "status.txt"]
            if log_files:
                log_file_path = os.path.join(full_directory_path, log_files[0])
                with open(log_file_path, 'r', encoding='utf-8') as file:
                    log_content = file.read()

                # Improved regex to handle multi-line messages
                # Pattern: [timestamp] **Role**: message
                message_pattern = re.compile(
                    r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \*\*(User|Bot|Assistant|System)\*\*: (.*?)(?=\n\[\d{4}-\d{2}-\d{2}|$)',
                    re.DOTALL
                )
                matches = message_pattern.findall(log_content)

                self.conversation = []
                for role, content in matches:
                    content = content.strip()
                    
                    # Handle media log entries - attach to previous message
                    if content.startswith("Generated selfie:"):
                        filename = content.replace("Generated selfie:", "").strip()
                        if self.conversation and self.conversation[-1]["role"] == "assistant":
                            if "media" not in self.conversation[-1]:
                                self.conversation[-1]["media"] = []
                            self.conversation[-1]["media"].append({
                                "type": "image",
                                "filename": filename,
                                "url": f"/output/{directory_path}/{filename}"
                            })
                        continue
                    
                    if content.startswith("Generated audio:"):
                        filename = content.replace("Generated audio:", "").strip()
                        if self.conversation and self.conversation[-1]["role"] == "assistant":
                            if "media" not in self.conversation[-1]:
                                self.conversation[-1]["media"] = []
                            self.conversation[-1]["media"].append({
                                "type": "audio",
                                "filename": filename,
                                "url": f"/output/{directory_path}/{filename}"
                            })
                        continue
                    
                    normalized_role = "user" if role == "User" else "assistant"
                    self.conversation.append({"role": normalized_role, "content": content})

                # Scan for video files that aren't logged to txt
                video_files = [f for f in os.listdir(full_directory_path) if f.endswith('.mp4')]
                if video_files and self.conversation:
                    # Find the last assistant message or create one for videos
                    last_assistant_idx = None
                    for i in range(len(self.conversation) - 1, -1, -1):
                        if self.conversation[i]["role"] == "assistant":
                            last_assistant_idx = i
                            break
                    
                    if last_assistant_idx is not None:
                        if "media" not in self.conversation[last_assistant_idx]:
                            self.conversation[last_assistant_idx]["media"] = []
                        
                        for video_file in sorted(video_files):
                            self.conversation[last_assistant_idx]["media"].append({
                                "type": "video",
                                "filename": video_file,
                                "url": f"/output/{directory_path}/{video_file}"
                            })

                # Reuse the existing folder (don't create new one)
                self.subfolder_path = full_directory_path
                self.log_file = log_file_path
                self.session_id = directory_path  # Use folder name as session ID

                return True
        return False
    
    def save_metadata(self):
        """Save session metadata to JSON file."""
        if not self.subfolder_path:
            return
        
        metadata = {
            "session_id": self.session_id,
            "character": self.character_name,
            "created_at": datetime.now().isoformat(),
            "last_message_preview": ""
        }
        
        metadata_path = os.path.join(self.subfolder_path, "session_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
    
    def update_metadata_preview(self):
        """Update the last message preview in metadata."""
        if not self.subfolder_path:
            return
        
        metadata_path = os.path.join(self.subfolder_path, "session_metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Get last assistant message for preview
                for msg in reversed(self.conversation):
                    if msg["role"] == "assistant":
                        preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                        metadata["last_message_preview"] = preview
                        break
                
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
            except Exception:
                pass  # Silently fail on metadata update errors
    
    @staticmethod
    def get_all_sessions(output_folder=None):
        """Get all sessions with their metadata."""
        if output_folder is None:
            output_folder = os.path.join(os.getcwd(), 'output')
        
        sessions = []
        if not os.path.exists(output_folder):
            return sessions
        
        for folder_name in os.listdir(output_folder):
            folder_path = os.path.join(output_folder, folder_name)
            if not os.path.isdir(folder_path):
                continue
            
            metadata_path = os.path.join(folder_path, "session_metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    metadata["folder_name"] = folder_name
                    sessions.append(metadata)
                except Exception:
                    pass
            else:
                # Legacy session without metadata - create basic info from folder
                log_files = [f for f in os.listdir(folder_path) if f.endswith('.txt') and f != 'status.txt']
                if log_files:
                    # Get folder creation time
                    created_time = datetime.fromtimestamp(os.path.getctime(folder_path))
                    sessions.append({
                        "session_id": folder_name,
                        "folder_name": folder_name,
                        "character": "Unknown",
                        "created_at": created_time.isoformat(),
                        "last_message_preview": "(Legacy session)"
                    })
        
        # Sort by created_at descending (most recent first)
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions

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
        # Note: DB media_path updates could be added here if needed
        self.save_message_to_log("Bot", f"Generated audio: {os.path.basename(audio_path)}")

    def get_last_audio_file(self):
        audio_files = [f for f in os.listdir(self.subfolder_path) if f.endswith('.mp3')]
        if audio_files:
            return os.path.join(self.subfolder_path, max(audio_files, key=lambda x: os.path.getctime(os.path.join(self.subfolder_path, x))))
        return None

    def set_last_selfie_path(self, image_path):
        self.last_selfie_path = image_path
        # Note: DB media_path updates could be added here if needed
        self.save_message_to_log("Bot", f"Generated selfie: {os.path.basename(image_path)}")

    def get_last_selfie_path(self):
        """Get the path of the most recent selfie image."""
        image_files = [f for f in os.listdir(self.subfolder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if image_files:
            return os.path.join(self.subfolder_path, max(image_files, key=lambda x: os.path.getctime(os.path.join(self.subfolder_path, x))))
        return None

    def get_last_audio_path(self):
        """Get the path of the last generated audio."""
        if self.last_audio_path and os.path.exists(self.last_audio_path):
            return self.last_audio_path
        return self.get_last_audio_file()
    
    def get_last_video_path(self):
        """Get the path of the last generated video."""
        if self.last_video_path and os.path.exists(self.last_video_path):
            return self.last_video_path
        # Fallback: find most recent mp4 in folder
        if self.subfolder_path:
            video_files = [f for f in os.listdir(self.subfolder_path) if f.endswith('.mp4')]
            if video_files:
                return os.path.join(self.subfolder_path, max(video_files, key=lambda x: os.path.getctime(os.path.join(self.subfolder_path, x))))
        return None
    
    def set_last_video_path(self, video_path):
        """Set the path of the last generated video."""
        self.last_video_path = video_path
        self.save_message_to_log("Bot", f"Generated video: {os.path.basename(video_path)}")

    def get_last_audio_and_selfie(self):
        return self.last_audio_path, self.last_selfie_path
