import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import sys
import json
import subprocess
import os
import signal
import psutil
import re
from datetime import datetime
from PIL import Image, ImageTk
import winsound
import threading
from users import users, list_users
from characters import characters
from config import CLAUDE_MODELS, OPENROUTER_MODELS, DEFAULT_CLAUDE_MODEL
from database_manager import DatabaseManager

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ConversationWindow:
    def __init__(self, root, process_info, session_id, db):
        self.window = ctk.CTkToplevel(root)
        self.window.title(f"{process_info.character} - Conversation with {process_info.user}")
        self.window.geometry("900x700")
        
        self.session_id = session_id
        self.db = db
        self.process_info = process_info
        self.output_dir = os.path.join("output", session_id)
        self.photo_references = []
        
        # Configure grid
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(0, weight=1)
        
        # Main container
        self.main_frame = ctk.CTkFrame(self.window)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # Chat display
        self.text = ctk.CTkTextbox(
            self.main_frame,
            font=('Segoe UI', 14),
            text_color='#E0E0E0',
            fg_color='#2B2B2B',
            wrap="word"
        )
        self.text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configure tags (simulated with colors in insert for now, as CTkTextbox has limited tag support compared to tk.Text)
        # Actually CTkTextbox is a wrapper around tk.Text, so we can access the underlying widget for tags
        self.text._textbox.tag_configure('timestamp', foreground='#808080', font=('Segoe UI', 10))
        self.text._textbox.tag_configure('user', foreground='#4CC2FF', font=('Segoe UI', 14, 'bold'))
        self.text._textbox.tag_configure('bot', foreground='#00E676', font=('Segoe UI', 14, 'bold'))
        self.text._textbox.tag_configure('italic', font=('Segoe UI', 14, 'italic'))
        
        # Controls
        self.controls_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, sticky="ew", pady=5)
        
        self.refresh_btn = ctk.CTkButton(self.controls_frame, text="Refresh", command=self.refresh, width=100)
        self.refresh_btn.pack(side="left", padx=5)
        
        self.copy_btn = ctk.CTkButton(self.controls_frame, text="Copy Log", command=self.copy_text, width=100, fg_color="transparent", border_width=1)
        self.copy_btn.pack(side="left", padx=5)
        
        self.auto_refresh = ctk.BooleanVar(value=True)
        self.auto_refresh_chk = ctk.CTkCheckBox(self.controls_frame, text="Auto-refresh", variable=self.auto_refresh)
        self.auto_refresh_chk.pack(side="left", padx=15)
        
        # Play button image
        play_img = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(play_img)
        draw.polygon([(5, 5), (15, 10), (5, 15)], fill='#00E676')
        self.play_button_img = ImageTk.PhotoImage(play_img)
        
        # Initial load
        self.refresh()
        self.check_auto_refresh()
        
        # Bring to front
        self.window.lift()
        self.window.focus_force()

    def check_auto_refresh(self):
        if self.auto_refresh.get():
            self.refresh()
        self.window.after(2000, self.check_auto_refresh)

    def format_message_with_italics(self, message, base_tag):
        """Format message with italics for text between asterisks"""
        current_pos = 0
        start_italic = message.find('*')
        
        while start_italic != -1:
            if start_italic > current_pos:
                text = message[current_pos:start_italic]
                self.text._textbox.insert(tk.END, text.replace('\\n', '\n'), base_tag)
            
            end_italic = message.find('*', start_italic + 1)
            if end_italic == -1:
                text = message[start_italic:]
                self.text._textbox.insert(tk.END, text.replace('\\n', '\n'), base_tag)
                break
            
            italic_text = message[start_italic + 1:end_italic]
            if italic_text:
                self.text._textbox.insert(tk.END, italic_text.replace('\\n', '\n'), (base_tag, 'italic'))
            
            current_pos = end_italic + 1
            start_italic = message.find('*', current_pos)
        
        if current_pos < len(message):
            text = message[current_pos:]
            self.text._textbox.insert(tk.END, text.replace('\\n', '\n'), base_tag)

    def refresh(self):
        try:
            # Save scroll position
            yview = self.text._textbox.yview()
            
            history = self.db.get_history(self.session_id)
            
            self.text.configure(state="normal")
            self.text.delete('1.0', tk.END)
            self.photo_references.clear()
            
            for msg in history:
                timestamp = msg['timestamp']
                role = msg['sender']
                message = msg['content']
                
                self.text._textbox.insert(tk.END, f"[{timestamp}] ", 'timestamp')
                
                if role.lower() == 'user':
                    self.text._textbox.insert(tk.END, f"{self.process_info.user}: ", 'user')
                    self.format_message_with_italics(message, 'user')
                else:
                    # Check for TTS
                    tts_pattern = r'Generated TTS file: (tts_response_\d{8}_\d{6}\.mp3|tts_v3_response_\d{8}_\d{6}\.mp3)'
                    tts_matches = re.findall(tts_pattern, message)
                    if tts_matches:
                        tts_path = os.path.join(self.output_dir, tts_matches[-1])
                        if os.path.exists(tts_path):
                            play_tag = f"play_{timestamp}"
                            self.text._textbox.image_create(tk.END, image=self.play_button_img, padx=5)
                            self.text._textbox.tag_add(play_tag, f"{self.text._textbox.index(tk.END)}-1c")
                            self.text._textbox.tag_bind(play_tag, '<Button-1>', 
                                             lambda e, path=tts_path: self.play_audio(path))

                    self.text._textbox.insert(tk.END, f"{self.process_info.character}: ", 'bot')
                    self.format_message_with_italics(message, 'bot')
                
                # Check for images
                if "Generated selfie:" in message:
                    try:
                        filename = message.split("Generated selfie:")[1].strip()
                        if filename in os.listdir(self.output_dir):
                            img_path = os.path.join(self.output_dir, filename)
                            photo = self.load_and_resize_image(img_path)
                            if photo:
                                self.text._textbox.insert(tk.END, "\n")
                                image_index = self.text._textbox.index(tk.END)
                                self.text._textbox.image_create(tk.END, image=photo)
                                tag_name = f"img_{filename}"
                                self.text._textbox.tag_add(tag_name, image_index, self.text._textbox.index(tk.END))
                                self.text._textbox.tag_bind(tag_name, '<Button-1>', 
                                                 lambda e, path=img_path: self.on_image_click(e, path))
                                self.text._textbox.insert(tk.END, "\n")
                    except IndexError:
                        pass
                
                self.text._textbox.insert(tk.END, "\n\n")
            
            # Restore scroll position if not at bottom
            # self.text._textbox.yview_moveto(yview[0]) 
            # Actually, for a chat, we usually want to auto-scroll to bottom unless user scrolled up.
            # For simplicity, let's just scroll to end for now.
            self.text.see(tk.END)
            self.text.configure(state="disabled")
            
        except Exception as e:
            print(f"Error refreshing conversation: {e}")

    def load_and_resize_image(self, image_path, max_width=300):
        try:
            image = Image.open(image_path)
            width, height = image.size
            if width > max_width:
                ratio = max_width / width
                new_width = max_width
                new_height = int(height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(image)
            self.photo_references.append(photo)
            return photo
        except Exception as e:
            print(f"Error loading image: {e}")
            return None

    def on_image_click(self, event, image_path):
        try:
            os.startfile(image_path)
        except Exception as e:
            print(f"Error opening image: {e}")

    def play_audio(self, audio_path):
        def play():
            try:
                winsound.PlaySound(audio_path, winsound.SND_FILENAME)
            except Exception as e:
                print(f"Error playing audio: {e}")
        threading.Thread(target=play, daemon=True).start()

    def copy_text(self):
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.text.get("1.0", tk.END))
            messagebox.showinfo("Copied", "Conversation log copied to clipboard.")
        except:
            pass

class ProcessInfo:
    def __init__(self, process, user, character):
        self.process = process
        self.user = user
        self.character = character
        self.start_time = datetime.now()
        self.last_message_time = None
        self.status = "Running"

class BotLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Discord Dreams Bot Launcher")
        
        # Center main window
        window_width = 1000
        window_height = 800
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.processes = []
        self.conversation_windows = {}
        self.db = DatabaseManager()
        self.user_settings = self.load_user_settings()
        
        # Main Layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_char = self.tabview.add("Character Settings")
        self.tab_llm = self.tabview.add("LLM Settings")
        
        self.setup_dashboard()
        self.setup_character_settings()
        self.setup_llm_settings()
        
        # Start process monitor
        self.update_process_list()
        
        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_user_settings(self):
        try:
            if os.path.exists("user_settings.json"):
                with open("user_settings.json", "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        return {}

    def setup_dashboard(self):
        self.tab_dashboard.grid_columnconfigure(0, weight=1)
        self.tab_dashboard.grid_rowconfigure(1, weight=1) # Process list expands
        
        # --- Quick Deploy Section ---
        deploy_frame = ctk.CTkFrame(self.tab_dashboard)
        deploy_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(deploy_frame, text="User:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=10)
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(deploy_frame, variable=self.user_var, values=list_users(), width=150)
        self.user_combo.pack(side="left", padx=5)
        if self.user_combo._values: self.user_combo.set(self.user_combo._values[0])
        
        ctk.CTkLabel(deploy_frame, text="Character:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=10)
        self.char_var = ctk.StringVar()
        self.char_combo = ctk.CTkComboBox(deploy_frame, variable=self.char_var, values=list(characters.keys()), width=150, command=self.on_character_select)
        self.char_combo.pack(side="left", padx=5)
        if self.char_combo._values: self.char_combo.set(self.char_combo._values[0])
        
        ctk.CTkLabel(deploy_frame, text="Remote Password:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=10)
        self.password_entry = ctk.CTkEntry(deploy_frame, width=150, show="*")
        self.password_entry.pack(side="left", padx=5)
        # Load saved password
        saved_pass = self.user_settings.get("remote_password", "")
        self.password_entry.insert(0, saved_pass)
        
        self.deploy_btn = ctk.CTkButton(deploy_frame, text="LAUNCH APP", command=self.deploy_bot, fg_color="#00E676", text_color="black", font=("Segoe UI", 12, "bold"))
        self.deploy_btn.pack(side="left", padx=20)
        
        # --- Process Monitor Section ---
        ctk.CTkLabel(self.tab_dashboard, text="Active Bots", font=("Segoe UI", 16, "bold")).grid(row=1, column=0, sticky="w", padx=10, pady=(10,0))
        
        # Scrollable frame for processes (replacing Treeview)
        self.process_list_frame = ctk.CTkScrollableFrame(self.tab_dashboard, label_text="Running Processes")
        self.process_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.process_list_frame.grid_columnconfigure(1, weight=1) # Character column expands
        
        # Footer buttons
        footer_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkButton(footer_frame, text="Stop All Bots", command=self.stop_all_bots, fg_color="#FF5252", hover_color="#D32F2F").pack(side="right", padx=5)
        ctk.CTkButton(footer_frame, text="Refresh List", command=self.update_process_list).pack(side="right", padx=5)

    def setup_character_settings(self):
        self.tab_char.grid_columnconfigure(1, weight=1)
        
        # System Prompt
        ctk.CTkLabel(self.tab_char, text="System Prompt:").grid(row=0, column=0, sticky="nw", padx=10, pady=10)
        self.system_prompt = ctk.CTkTextbox(self.tab_char, height=100)
        self.system_prompt.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        
        # Image Prompt
        ctk.CTkLabel(self.tab_char, text="Image Prompt:").grid(row=1, column=0, sticky="nw", padx=10, pady=10)
        self.image_prompt = ctk.CTkTextbox(self.tab_char, height=80)
        self.image_prompt.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        
        # Scenario
        ctk.CTkLabel(self.tab_char, text="Scenario:").grid(row=2, column=0, sticky="nw", padx=10, pady=10)
        self.scenario = ctk.CTkTextbox(self.tab_char, height=80)
        self.scenario.grid(row=2, column=1, sticky="ew", padx=10, pady=10)
        
        # Voice Settings Frame
        voice_frame = ctk.CTkFrame(self.tab_char)
        voice_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        voice_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(voice_frame, text="TTS URL:").grid(row=0, column=0, padx=10, pady=10)
        self.tts_url = ctk.CTkEntry(voice_frame)
        self.tts_url.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        
        settings_grid = ctk.CTkFrame(voice_frame, fg_color="transparent")
        settings_grid.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)
        
        ctk.CTkLabel(settings_grid, text="Stability:").pack(side="left", padx=5)
        self.stability = ctk.CTkEntry(settings_grid, width=60)
        self.stability.pack(side="left", padx=5)
        
        ctk.CTkLabel(settings_grid, text="Similarity:").pack(side="left", padx=5)
        self.similarity = ctk.CTkEntry(settings_grid, width=60)
        self.similarity.pack(side="left", padx=5)
        
        ctk.CTkLabel(settings_grid, text="Style:").pack(side="left", padx=5)
        self.style = ctk.CTkEntry(settings_grid, width=60)
        self.style.pack(side="left", padx=5)
        
        # Save Button
        ctk.CTkButton(self.tab_char, text="Save Changes", command=self.save_changes, fg_color="#448AFF").grid(row=4, column=0, columnspan=2, pady=20)

    def setup_llm_settings(self):
        self.tab_llm.grid_columnconfigure(1, weight=1)
        
        # Main LLM
        main_frame = ctk.CTkFrame(self.tab_llm)
        main_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=20)
        main_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(main_frame, text="Main Conversation LLM", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        
        ctk.CTkLabel(main_frame, text="Provider:").grid(row=1, column=0, padx=10, pady=10)
        self.main_provider_var = ctk.StringVar(value=self.user_settings.get("main_provider", "OpenRouter"))
        self.main_provider_combo = ctk.CTkComboBox(main_frame, variable=self.main_provider_var, values=["Anthropic", "OpenRouter", "LMStudio"], command=self.on_main_provider_select)
        self.main_provider_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(main_frame, text="Model:").grid(row=2, column=0, padx=10, pady=10)
        self.main_model_var = ctk.StringVar(value=self.user_settings.get("main_model", "deepseek/deepseek-chat-v3.1 (deep3.1)"))
        self.main_model_combo = ctk.CTkComboBox(main_frame, variable=self.main_model_var, width=300)
        self.main_model_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=10)
        
        # Media LLM
        media_frame = ctk.CTkFrame(self.tab_llm)
        media_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=20)
        media_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(media_frame, text="Media Generation LLM", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=10)
        
        ctk.CTkLabel(media_frame, text="Provider:").grid(row=1, column=0, padx=10, pady=10)
        self.media_provider_var = ctk.StringVar(value=self.user_settings.get("media_provider", "OpenRouter"))
        self.media_provider_combo = ctk.CTkComboBox(media_frame, variable=self.media_provider_var, values=["OpenRouter"], command=self.on_media_provider_select)
        self.media_provider_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(media_frame, text="Model:").grid(row=2, column=0, padx=10, pady=10)
        self.media_model_var = ctk.StringVar(value=self.user_settings.get("media_model", "deepseek/deepseek-chat-v3.1 (deep3.1)"))
        self.media_model_combo = ctk.CTkComboBox(media_frame, variable=self.media_model_var, width=300)
        self.media_model_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=10)
        
        # Initialize lists
        self.update_main_model_list()
        self.update_media_model_list()

    def update_process_list(self):
        # Clear existing widgets in scrollable frame
        for widget in self.process_list_frame.winfo_children():
            widget.destroy()
            
        # Re-populate
        for process_info in self.processes[:]:
            # Check status
            if process_info.process.poll() is not None:
                process_info.status = "Stopped"
                self.processes.remove(process_info)
                continue
                
            # Create row frame
            row = ctk.CTkFrame(self.process_list_frame)
            row.pack(fill="x", padx=5, pady=5)
            
            # Info
            status_color = "#00E676" if process_info.status == "Running" else "#FFC107"
            ctk.CTkLabel(row, text=f"PID: {process_info.process.pid}", width=60).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=f"User: {process_info.user}", width=80).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=f"Char: {process_info.character}", width=80, font=("Segoe UI", 12, "bold")).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=process_info.status, text_color=status_color, width=80).pack(side="left", padx=5)
            
            # Actions
            ctk.CTkButton(row, text="Open Chat", width=80, 
                        command=lambda p=process_info.process.pid: self.open_chat(p)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="Stop", width=60, fg_color="#FF5252", hover_color="#D32F2F",
                        command=lambda p=process_info: self.stop_process(p)).pack(side="right", padx=5)

        self.root.after(2000, self.update_process_list)

    def open_chat(self, pid):
        process_info = next((p for p in self.processes if p.process.pid == pid), None)
        if not process_info: return
        
        if pid in self.conversation_windows:
            self.conversation_windows[pid].window.lift()
            self.conversation_windows[pid].window.focus_force()
            return
            
        # Find session ID
        session_id = None
        output_dir = os.path.join("output")
        if os.path.exists(output_dir):
            subdirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
            if subdirs:
                # Heuristic: assume latest modified folder is the session
                session_id = max(subdirs, key=lambda d: os.path.getctime(os.path.join(output_dir, d)))
        
        if session_id:
            window = ConversationWindow(self.root, process_info, session_id, self.db)
            self.conversation_windows[pid] = window
            window.window.protocol("WM_DELETE_WINDOW", lambda: self.on_chat_close(pid))
        else:
            messagebox.showwarning("No Log", "Could not find conversation log.")

    def on_chat_close(self, pid):
        if pid in self.conversation_windows:
            self.conversation_windows[pid].window.destroy()
            del self.conversation_windows[pid]

    def deploy_bot(self):
        user = self.user_var.get()
        char = self.char_var.get()
        if not user or not char:
            messagebox.showerror("Error", "Select user and character")
            return
            
        try:
            # Open browser
            import webbrowser
            import urllib.parse
            query_params = urllib.parse.urlencode({'user': user, 'character': char})
            webbrowser.open(f"http://localhost:8000?{query_params}")
            
            # Use cmd /k to keep window open on error for debugging
            if os.name == 'nt':
                cmd = ["cmd", "/k", sys.executable, "server.py"]
                process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                cmd = [sys.executable, "server.py"]
                process = subprocess.Popen(cmd, preexec_fn=os.setsid)
                
            p_info = ProcessInfo(process, user, char)
            self.processes.append(p_info)
            self.update_process_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to deploy: {e}")

    def stop_process(self, process_info):
        try:
            parent = psutil.Process(process_info.process.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            if process_info in self.processes:
                self.processes.remove(process_info)
            self.update_process_list()
        except Exception as e:
            print(f"Error stopping: {e}")

    def stop_all_bots(self):
        for p in self.processes[:]:
            self.stop_process(p)

    def on_character_select(self, choice):
        if choice in characters:
            data = characters[choice]
            self.system_prompt.delete("1.0", "end")
            self.system_prompt.insert("1.0", data.get("system_prompt", ""))
            
            self.image_prompt.delete("1.0", "end")
            self.image_prompt.insert("1.0", data.get("image_prompt", ""))
            
            self.scenario.delete("1.0", "end")
            self.scenario.insert("1.0", data.get("scenario", ""))
            
            self.tts_url.delete(0, "end")
            self.tts_url.insert(0, data.get("tts_url", ""))
            
            vs = data.get("voice_settings", {})
            self.stability.delete(0, "end"); self.stability.insert(0, str(vs.get("stability", 0.4)))
            self.similarity.delete(0, "end"); self.similarity.insert(0, str(vs.get("similarity_boost", 0.45)))
            self.style.delete(0, "end"); self.style.insert(0, str(vs.get("style", 0.5)))

    def save_changes(self):
        char = self.char_var.get()
        if not char: return
        
        try:
            characters[char].update({
                "system_prompt": self.system_prompt.get("1.0", "end-1c"),
                "image_prompt": self.image_prompt.get("1.0", "end-1c"),
                "scenario": self.scenario.get("1.0", "end-1c"),
                "tts_url": self.tts_url.get(),
                "voice_settings": {
                    "stability": float(self.stability.get()),
                    "similarity_boost": float(self.similarity.get()),
                    "style": float(self.style.get())
                }
            })
            
            with open("characters.py", "w", encoding="utf-8") as f:
                f.write("characters = " + json.dumps(characters, indent=4, ensure_ascii=False))
            
            # Save LLM Settings
            settings = {
                "main_provider": self.main_provider_var.get(),
                "main_model": self.main_model_var.get(),
                "media_provider": self.media_provider_var.get(),
                "media_model": self.media_model_var.get(),
                "remote_password": self.password_entry.get()
            }
            with open("user_settings.json", "w") as f:
                json.dump(settings, f, indent=4)

            messagebox.showinfo("Success", "Changes saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def update_main_model_list(self, _=None):
        provider = self.main_provider_var.get()
        if provider == "Anthropic":
            self.main_model_combo.configure(values=[f"{n} ({c})" for n, c in CLAUDE_MODELS.items()])
        elif provider == "OpenRouter":
            self.main_model_combo.configure(values=[f"{n} ({c})" for n, c in OPENROUTER_MODELS.items()])
        else:
            self.main_model_combo.configure(values=["default"])
        
        current_val = self.main_model_var.get()
        if current_val and current_val in self.main_model_combo._values:
            self.main_model_combo.set(current_val)
        elif self.main_model_combo._values:
            self.main_model_combo.set(self.main_model_combo._values[0])

    def update_media_model_list(self, _=None):
        self.media_model_combo.configure(values=[f"{n} ({c})" for n, c in OPENROUTER_MODELS.items()])
        
        current_val = self.media_model_var.get()
        if current_val and current_val in self.media_model_combo._values:
            self.media_model_combo.set(current_val)
        elif self.media_model_combo._values:
            self.media_model_combo.set(self.media_model_combo._values[0])

    def on_main_provider_select(self, choice):
        self.update_main_model_list()

    def on_media_provider_select(self, choice):
        self.update_media_model_list()

    def on_closing(self):
        self.stop_all_bots()
        self.root.destroy()
        sys.exit(0)

class SplashScreen:
    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        
        self.window = ctk.CTkToplevel(root)
        self.window.overrideredirect(True) # Frameless
        
        # Default size if image fails
        width, height = 500, 400
        
        # Load Image
        try:
            if os.path.exists("dd.png"):
                image = Image.open("dd.png")
                width, height = image.size
                # Image Label (Background)
                self.ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(width, height))
                self.img_label = ctk.CTkLabel(self.window, image=self.ctk_image, text="")
                self.img_label.place(x=0, y=0, relwidth=1, relheight=1)
            else:
                self.window.geometry(f"{width}x{height}")
                self.window.configure(fg_color="#1a1a1a")
                ctk.CTkLabel(self.window, text="Discord Dreams", font=("Segoe UI", 32, "bold")).place(relx=0.5, rely=0.4, anchor="center")
        except Exception as e:
            print(f"Error loading splash image: {e}")
            self.window.geometry(f"{width}x{height}")
            self.window.configure(fg_color="#1a1a1a")
            ctk.CTkLabel(self.window, text="Discord Dreams", font=("Segoe UI", 32, "bold")).place(relx=0.5, rely=0.4, anchor="center")

        # Center window on screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        # Button (Overlay)
        self.btn = ctk.CTkButton(
            self.window, 
            text="Click to Open Launcher", 
            font=("Segoe UI", 14, "bold"),
            fg_color="#00E676", 
            text_color="black",
            hover_color="#00C853",
            command=self.enter_launcher,
            height=40,
            bg_color="transparent",
            background_corner_colors=None # Try to make corners transparent if possible, though CTkButton is rectangular
        )
        # Place at bottom center
        self.btn.place(relx=0.5, rely=0.9, anchor="center")
        
        self.window.lift()
        self.window.focus_force()

    def enter_launcher(self):
        self.window.destroy()
        self.on_complete()

def launch_main_app():
    app.deiconify() # Show main window
    global launcher
    launcher = BotLauncher(app)

if __name__ == "__main__":
    app = ctk.CTk()
    app.withdraw() # Hide main window initially
    
    splash = SplashScreen(app, on_complete=launch_main_app)
    
    app.mainloop()
