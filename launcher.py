import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
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
from config import CLAUDE_MODELS, OPENROUTER_MODELS, DEFAULT_CLAUDE_MODEL, IMAGE_WIDTH, IMAGE_HEIGHT, IMAGE_STEPS, IMAGE_GUIDANCE_SCALE, IMAGE_SAMPLER, DEFAULT_SD_MODEL
from database_manager import DatabaseManager
from chub_importer import ChubImporter

# Set theme to match web UI (Glassmorphism Premium)
ctk.set_appearance_mode("Dark")

# Custom color scheme matching web UI (Refined Slate Palette)
COLORS = {
    "bg_primary": "#0f172a",        # Slate 900 (Main Background)
    "bg_secondary": "#1e293b",      # Slate 800 (Secondary/Panels)
    "glass_panel": "#1e293b",       # Slate 800 (Unified with secondary for cleaner look)
    "input_bg": "#334155",          # Slate 700 (Input fields)
    "accent_cyan": "#0ea5e9",       # Sky 500 (Slightly deeper cyan for better contrast)
    "accent_purple": "#6366f1",     # Indigo 500 (Smoother purple)
    "text_primary": "#f8fafc",      # Slate 50
    "text_secondary": "#94a3b8",    # Slate 400
    "border": "#334155",            # Slate 700
    "success": "#22c55e",           # Green 500
    "error": "#ef4444",             # Red 500
    "hover": "#475569"              # Slate 600
}

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
        self.root.title("Reverie Launcher")
        
        # Apply custom background color
        self.root.configure(fg_color=COLORS["bg_primary"])
        
        # Center main window
        window_width = 1000
        window_height = 800
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Start maximized on Windows
        self.root.state('zoomed')
        
        self.processes = []
        self.conversation_windows = {}
        self.db = DatabaseManager()
        self.chub_importer = ChubImporter()
        self.user_settings = self.load_user_settings()
        
        # Load imported characters into the characters dict
        imported = self.chub_importer.load_imported()
        characters.update(imported)
        
        # Main Layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        self.tabview = ctk.CTkTabview(
            self.root,
            fg_color=COLORS["glass_panel"],
            segmented_button_fg_color=COLORS["bg_primary"],
            segmented_button_selected_color=COLORS["accent_cyan"],
            segmented_button_selected_hover_color=COLORS["accent_purple"],
            segmented_button_unselected_color=COLORS["bg_primary"],
            segmented_button_unselected_hover_color=COLORS["hover"],
            text_color=COLORS["text_primary"]
        )
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
        self.tab_dashboard.grid_rowconfigure(1, weight=1)  # Process list expands
        
        # --- Quick Deploy Section ---
        deploy_frame = ctk.CTkFrame(
            self.tab_dashboard,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10
        )
        deploy_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(deploy_frame, text="User:", font=("Segoe UI", 12, "bold"), text_color=COLORS["text_primary"]).pack(side="left", padx=10)
        self.user_var = ctk.StringVar()
        self.user_combo = ctk.CTkComboBox(
            deploy_frame,
            variable=self.user_var,
            values=list_users(),
            width=150,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["accent_cyan"],
            button_hover_color=COLORS["accent_purple"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["hover"],
            dropdown_text_color=COLORS["text_primary"]
        )
        self.user_combo.pack(side="left", padx=5)
        if self.user_combo._values:
            self.user_combo.set(self.user_combo._values[0])
        
        ctk.CTkLabel(deploy_frame, text="Character:", font=("Segoe UI", 12, "bold"), text_color=COLORS["text_primary"]).pack(side="left", padx=10)
        self.char_var = ctk.StringVar()
        self.char_combo = ctk.CTkComboBox(
            deploy_frame,
            variable=self.char_var,
            values=list(characters.keys()),
            width=150,
            command=self.on_character_select,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["accent_cyan"],
            button_hover_color=COLORS["accent_purple"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["hover"],
            dropdown_text_color=COLORS["text_primary"]
        )
        self.char_combo.pack(side="left", padx=5)
        if self.char_combo._values:
            self.char_combo.set(self.char_combo._values[0])
        
        ctk.CTkLabel(deploy_frame, text="Remote Password:", font=("Segoe UI", 12, "bold"), text_color=COLORS["text_primary"]).pack(side="left", padx=10)
        self.password_entry = ctk.CTkEntry(
            deploy_frame,
            width=150,
            show="*",
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.password_entry.pack(side="left", padx=5)
        # Load saved password
        saved_pass = self.user_settings.get("remote_password", "")
        self.password_entry.insert(0, saved_pass)

        self.use_ngrok_var = ctk.BooleanVar(value=self.user_settings.get("use_ngrok", False))
        self.use_ngrok_chk = ctk.CTkCheckBox(
            deploy_frame,
            text="Public Link",
            variable=self.use_ngrok_var,
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["accent_cyan"],
            hover_color=COLORS["accent_purple"]
        )
        self.use_ngrok_chk.pack(side="left", padx=10)
        
        self.deploy_btn = ctk.CTkButton(
            deploy_frame,
            text="LAUNCH APP",
            command=self.deploy_bot,
            fg_color=COLORS["accent_cyan"],
            hover_color=COLORS["accent_purple"],
            text_color="white",
            font=("Segoe UI", 12, "bold")
        )
        self.deploy_btn.pack(side="left", padx=20)
        
        # Import Character Button
        self.import_btn = ctk.CTkButton(
            deploy_frame,
            text="Import Character",
            command=self.import_chub_character,
            fg_color=COLORS["input_bg"],
            hover_color=COLORS["hover"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            font=("Segoe UI", 11)
        )
        self.import_btn.pack(side="left", padx=5)
        
        # Delete Imported Character Button
        self.delete_char_btn = ctk.CTkButton(
            deploy_frame,
            text="Delete Character",
            command=self.delete_imported_character,
            fg_color=COLORS["error"],
            hover_color="#dc2626",
            text_color="white",
            font=("Segoe UI", 11)
        )
        self.delete_char_btn.pack(side="left", padx=5)
        # --- Process Monitor Section ---
        ctk.CTkLabel(
            self.tab_dashboard,
            text="Active Bots",
            font=("Segoe UI", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(10, 0))
        
        # Scrollable frame for processes
        self.process_list_frame = ctk.CTkScrollableFrame(
            self.tab_dashboard,
            label_text="Running Processes",
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            border_width=1,
            label_text_color=COLORS["text_secondary"],
            scrollbar_button_color=COLORS["accent_cyan"],
            scrollbar_button_hover_color=COLORS["accent_purple"]
        )
        self.process_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.process_list_frame.grid_columnconfigure(1, weight=1)  # Character column expands
        
        # Footer buttons
        footer_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkButton(
            footer_frame,
            text="Stop All Bots",
            command=self.stop_all_bots,
            fg_color=COLORS["error"],
            hover_color="#dc2626"
        ).pack(side="right", padx=5)
        
        ctk.CTkButton(
            footer_frame,
            text="Refresh List",
            command=self.update_process_list,
            fg_color=COLORS["input_bg"],
            hover_color=COLORS["hover"],
            border_color=COLORS["border"],
            border_width=1
        ).pack(side="right", padx=5)

    def setup_character_settings(self):
        self.tab_char.grid_columnconfigure(1, weight=1)
        self.tab_char.grid_rowconfigure(0, weight=1)  # Allow System Prompt to expand vertically
        
        # System Prompt
        ctk.CTkLabel(
            self.tab_char,
            text="System Prompt:",
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="nw", padx=10, pady=10)
        self.system_prompt = ctk.CTkTextbox(
            self.tab_char,
            height=300,  # Increased default height
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"]
        )
        self.system_prompt.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)  # sticky="nsew" to fill space
        
        # Image Prompt
        ctk.CTkLabel(
            self.tab_char,
            text="Image Prompt:",
            text_color=COLORS["text_primary"]
        ).grid(row=1, column=0, sticky="nw", padx=10, pady=10)
        self.image_prompt = ctk.CTkTextbox(
            self.tab_char,
            height=40,  # Reduced to ~1 line
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"]
        )
        self.image_prompt.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        
        # Scenario
        ctk.CTkLabel(
            self.tab_char,
            text="Scenario:",
            text_color=COLORS["text_primary"]
        ).grid(row=2, column=0, sticky="nw", padx=10, pady=10)
        self.scenario = ctk.CTkTextbox(
            self.tab_char,
            height=60,  # Slightly reduced
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"]
        )
        self.scenario.grid(row=2, column=1, sticky="ew", padx=10, pady=10)
        
        # Voice Settings Frame
        voice_frame = ctk.CTkFrame(
            self.tab_char,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10
        )
        voice_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        voice_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            voice_frame,
            text="TTS URL:",
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, padx=10, pady=10)
        self.tts_url = ctk.CTkEntry(
            voice_frame,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.tts_url.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        
        settings_grid = ctk.CTkFrame(voice_frame, fg_color="transparent")
        settings_grid.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)
        
        ctk.CTkLabel(settings_grid, text="Stability:", text_color=COLORS["text_primary"]).pack(side="left", padx=5)
        self.stability = ctk.CTkEntry(
            settings_grid,
            width=60,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.stability.pack(side="left", padx=5)
        
        ctk.CTkLabel(settings_grid, text="Similarity:", text_color=COLORS["text_primary"]).pack(side="left", padx=5)
        self.similarity = ctk.CTkEntry(
            settings_grid,
            width=60,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.similarity.pack(side="left", padx=5)
        
        ctk.CTkLabel(settings_grid, text="Style:", text_color=COLORS["text_primary"]).pack(side="left", padx=5)
        self.style = ctk.CTkEntry(
            settings_grid,
            width=60,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.style.pack(side="left", padx=5)
        
        # Save Button
        ctk.CTkButton(
            self.tab_char,
            text="Save Changes",
            command=self.save_changes,
            fg_color=COLORS["accent_cyan"],
            hover_color=COLORS["accent_purple"]
        ).grid(row=4, column=0, columnspan=2, pady=20)

    def setup_llm_settings(self):
        self.tab_llm.grid_columnconfigure(1, weight=1)
        
        # Main LLM
        main_frame = ctk.CTkFrame(
            self.tab_llm,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10
        )
        main_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=20)
        main_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            main_frame,
            text="Main Conversation LLM",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, columnspan=2, pady=10)
        
        ctk.CTkLabel(main_frame, text="Provider:", text_color=COLORS["text_primary"]).grid(row=1, column=0, padx=10, pady=10)
        self.main_provider_var = ctk.StringVar(value=self.user_settings.get("main_provider", "OpenRouter"))
        self.main_provider_combo = ctk.CTkComboBox(
            main_frame,
            variable=self.main_provider_var,
            values=["Anthropic", "OpenRouter", "LMStudio"],
            command=self.on_main_provider_select,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["accent_cyan"],
            button_hover_color=COLORS["accent_purple"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["hover"],
            dropdown_text_color=COLORS["text_primary"]
        )
        self.main_provider_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(main_frame, text="Model:", text_color=COLORS["text_primary"]).grid(row=2, column=0, padx=10, pady=10)
        self.main_model_var = ctk.StringVar(value=self.user_settings.get("main_model", "deepseek/deepseek-chat-v3.1 (deep3.1)"))
        self.main_model_combo = ctk.CTkComboBox(
            main_frame,
            variable=self.main_model_var,
            width=300,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["accent_cyan"],
            button_hover_color=COLORS["accent_purple"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["hover"],
            dropdown_text_color=COLORS["text_primary"]
        )
        self.main_model_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=10)
        
        # Media LLM
        media_frame = ctk.CTkFrame(
            self.tab_llm,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10
        )
        media_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=20)
        media_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            media_frame,
            text="Media Generation LLM",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, columnspan=2, pady=10)
        
        ctk.CTkLabel(media_frame, text="Provider:", text_color=COLORS["text_primary"]).grid(row=1, column=0, padx=10, pady=10)
        self.media_provider_var = ctk.StringVar(value=self.user_settings.get("media_provider", "OpenRouter"))
        self.media_provider_combo = ctk.CTkComboBox(
            media_frame,
            variable=self.media_provider_var,
            values=["OpenRouter"],
            command=self.on_media_provider_select,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["accent_cyan"],
            button_hover_color=COLORS["accent_purple"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["hover"],
            dropdown_text_color=COLORS["text_primary"]
        )
        self.media_provider_combo.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(media_frame, text="Model:", text_color=COLORS["text_primary"]).grid(row=2, column=0, padx=10, pady=10)
        self.media_model_var = ctk.StringVar(value=self.user_settings.get("media_model", "deepseek/deepseek-chat-v3.1 (deep3.1)"))
        self.media_model_combo = ctk.CTkComboBox(
            media_frame,
            variable=self.media_model_var,
            width=300,
            fg_color=COLORS["input_bg"],
            button_color=COLORS["accent_cyan"],
            button_hover_color=COLORS["accent_purple"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_hover_color=COLORS["hover"],
            dropdown_text_color=COLORS["text_primary"]
        )
        self.media_model_combo.grid(row=2, column=1, sticky="ew", padx=10, pady=10)

        # Ngrok Settings
        ngrok_frame = ctk.CTkFrame(
            self.tab_llm,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10
        )
        ngrok_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=20)
        ngrok_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            ngrok_frame,
            text="Ngrok Configuration",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).grid(row=0, column=0, columnspan=2, pady=10)

        ctk.CTkLabel(ngrok_frame, text="Auth Token:", text_color=COLORS["text_primary"]).grid(row=1, column=0, padx=10, pady=10)
        self.ngrok_token_entry = ctk.CTkEntry(
            ngrok_frame,
            show="*",
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.ngrok_token_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        self.ngrok_token_entry.insert(0, self.user_settings.get("ngrok_auth_token", ""))

        # Initialize model lists based on current provider
        self.on_main_provider_select(self.main_provider_var.get())
        self.on_media_provider_select(self.media_provider_var.get())
    
    def on_main_provider_select(self, provider):
        """Update main model dropdown based on selected provider"""
        if provider == "OpenRouter":
            # Format: "model/path (shortName)"
            model_options = [f"{full_name} ({short_code})" for full_name, short_code in OPENROUTER_MODELS.items()]
            self.main_model_combo.configure(values=model_options)
            # Set saved value if it exists
            saved_model = self.user_settings.get("main_model", "")
            if saved_model in model_options:
                self.main_model_combo.set(saved_model)
            elif model_options:
                self.main_model_combo.set(model_options[0])
        elif provider == "Anthropic":
            model_options = [f"{full_name} ({short_code})" for full_name, short_code in CLAUDE_MODELS.items()]
            self.main_model_combo.configure(values=model_options)
            saved_model = self.user_settings.get("main_model", "")
            if saved_model in model_options:
                self.main_model_combo.set(saved_model)
            elif model_options:
                self.main_model_combo.set(model_options[0])
        elif provider == "LMStudio":
            self.main_model_combo.configure(values=["Local Model"])
            self.main_model_combo.set("Local Model")
    
    def on_media_provider_select(self, provider):
        """Update media model dropdown based on selected provider"""
        if provider == "OpenRouter":
            model_options = [f"{full_name} ({short_code})" for full_name, short_code in OPENROUTER_MODELS.items()]
            self.media_model_combo.configure(values=model_options)
            saved_model = self.user_settings.get("media_model", "")
            if saved_model in model_options:
                self.media_model_combo.set(saved_model)
            elif model_options:
                self.media_model_combo.set(model_options[0])

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
            env = os.environ.copy()
            env["USE_NGROK"] = "true" if self.use_ngrok_var.get() else "false"
            env["NGROK_AUTH_TOKEN"] = self.ngrok_token_entry.get()
            
            # Save settings
            self.user_settings["use_ngrok"] = self.use_ngrok_var.get()
            self.user_settings["ngrok_auth_token"] = self.ngrok_token_entry.get()
            self.user_settings["remote_password"] = self.password_entry.get()
            with open("user_settings.json", "w") as f:
                json.dump(self.user_settings, f, indent=4)

            if os.name == 'nt':
                cmd = ["cmd", "/k", sys.executable, "server.py"]
                process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE, env=env)
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
                f.write("characters = " + json.dumps(characters, indent=4, ensure_ascii=False).replace("false", "False").replace("true", "True").replace("null", "None"))
            
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

    def import_chub_character(self):
        """Import a character from a Chub.ai JSON file with enhanced dialog."""
        # Open file picker
        file_path = filedialog.askopenfilename(
            title="Select Chub Character Card",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Parse the Chub card
            chub_data = self.chub_importer.parse(file_path)
            char_name = chub_data.get('name', 'Unknown')
            
            # Get scenario options
            scenario_options = self.chub_importer.get_scenario_options(chub_data)
            
            # If no scenarios exist, generate some with LLM
            if not scenario_options or scenario_options == ["No scenarios available"]:
                scenario_options = ["⏳ Generating scenarios with LLM..."]
                needs_scenario_generation = True
            else:
                needs_scenario_generation = False
            
            # Create enhanced import dialog
            dialog = ctk.CTkToplevel(self.root)
            dialog.title(f"Import: {char_name}")
            dialog.geometry("900x750")
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.configure(fg_color=COLORS["bg_primary"])
            
            # Center dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() - 900) // 2
            y = (dialog.winfo_screenheight() - 750) // 2
            dialog.geometry(f"+{x}+{y}")
            
            # Main scrollable container
            main_frame = ctk.CTkScrollableFrame(
                dialog,
                fg_color=COLORS["bg_secondary"],
                scrollbar_button_color=COLORS["accent_cyan"]
            )
            main_frame.pack(fill="both", expand=True, padx=15, pady=15)
            
            # Character name header
            ctk.CTkLabel(
                main_frame,
                text=f"Importing: {char_name}",
                font=("Segoe UI", 20, "bold"),
                text_color=COLORS["text_primary"]
            ).pack(pady=(10, 20))
            
            # --- System Prompt Preview (Scrollable) ---
            ctk.CTkLabel(
                main_frame,
                text="Character Description (System Prompt Preview):",
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS["text_primary"]
            ).pack(anchor="w", padx=10)
            
            desc_textbox = ctk.CTkTextbox(
                main_frame,
                height=150,
                fg_color=COLORS["input_bg"],
                border_color=COLORS["border"],
                border_width=1,
                text_color=COLORS["text_secondary"],
                wrap="word"
            )
            desc_textbox.pack(fill="x", padx=10, pady=(5, 15))
            desc_textbox.insert("1.0", chub_data.get('description', 'No description available'))
            desc_textbox.configure(state="disabled")
            
            # --- Image Prompt (Editable) ---
            ctk.CTkLabel(
                main_frame,
                text="Image Prompt (for selfie generation):",
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS["text_primary"]
            ).pack(anchor="w", padx=10)
            
            image_prompt_textbox = ctk.CTkTextbox(
                main_frame,
                height=60,
                fg_color=COLORS["input_bg"],
                border_color=COLORS["border"],
                border_width=1,
                text_color=COLORS["text_primary"],
                wrap="word"
            )
            image_prompt_textbox.pack(fill="x", padx=10, pady=(5, 5))
            image_prompt_textbox.insert("1.0", "Generating image prompt...")
            
            # Status label for LLM generation
            status_label = ctk.CTkLabel(
                main_frame,
                text="⏳ Generating image prompt with LLM...",
                text_color=COLORS["accent_cyan"],
                font=("Segoe UI", 10)
            )
            status_label.pack(anchor="w", padx=10, pady=(0, 10))
            
            # --- Reference Image Section ---
            ref_frame = ctk.CTkFrame(main_frame, fg_color=COLORS["bg_primary"])
            ref_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(
                ref_frame,
                text="Reference Image (for face swap):",
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS["text_primary"]
            ).pack(anchor="w", padx=10, pady=(10, 5))
            
            # Image preview placeholder
            ref_image_label = ctk.CTkLabel(
                ref_frame,
                text="No reference image yet.\nClick 'Generate Preview' after the image prompt is ready.",
                width=200,
                height=200,
                fg_color=COLORS["input_bg"],
                corner_radius=10,
                text_color=COLORS["text_secondary"]
            )
            ref_image_label.pack(pady=10)
            
            # Store reference for the generated image path
            ref_image_path = {"path": None}
            photo_ref = {"photo": None}  # Keep reference to prevent garbage collection
            
            def generate_reference_image():
                """Generate a reference portrait image using Stable Diffusion."""
                import aiohttp
                import asyncio
                import base64
                from PIL import Image
                import io
                
                prompt = image_prompt_textbox.get("1.0", "end-1c").strip()
                if not prompt or "Generating" in prompt:
                    messagebox.showwarning("Wait", "Please wait for the image prompt to be generated first.")
                    return
                
                # Update status
                ref_image_label.configure(text="⏳ Generating reference image...")
                dialog.update()
                
                async def generate():
                    # Portrait prompt - selfie-style for face swap reference
                    portrait_prompt = f"amateur selfie photo of {prompt}, looking at camera, natural lighting, upper body visible, casual pose, high quality"
                    
                    # Use XL mode params from config with model override
                    payload = {
                        "prompt": portrait_prompt,
                        "steps": IMAGE_STEPS,
                        "sampler_name": IMAGE_SAMPLER,
                        "scheduler": "Karras",
                        "width": IMAGE_WIDTH,
                        "height": IMAGE_HEIGHT,
                        "seed": -1,
                        "cfg_scale": IMAGE_GUIDANCE_SCALE,
                        "override_settings": {
                            "sd_model_checkpoint": DEFAULT_SD_MODEL,
                            "sd_vae": "Automatic",
                            "forge_additional_modules": [],
                            "CLIP_stop_at_last_layers": 2
                        }
                    }
                    
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                "http://127.0.0.1:7860/sdapi/v1/txt2img",
                                json=payload,
                                headers={'Content-Type': 'application/json'},
                                timeout=aiohttp.ClientTimeout(total=120)
                            ) as response:
                                if response.status == 200:
                                    r = await response.json()
                                    if 'images' in r and len(r['images']) > 0:
                                        return r['images'][0]
                    except Exception as e:
                        print(f"Error generating reference image: {e}")
                    return None
                
                # Run async generation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    image_data = loop.run_until_complete(generate())
                finally:
                    loop.close()
                
                if image_data:
                    # Decode and display
                    image_bytes = base64.b64decode(image_data)
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # Save to faces folder
                    safe_name = "".join(c for c in char_name if c.isalnum() or c in (' ', '_')).strip().replace(' ', '_')
                    faces_folder = f"E:\\dll\\Faces_m\\{safe_name}"
                    os.makedirs(faces_folder, exist_ok=True)
                    
                    image_path = os.path.join(faces_folder, "reference_1.png")
                    image.save(image_path)
                    ref_image_path["path"] = faces_folder
                    
                    # Display thumbnail in dialog
                    display_image = image.copy()
                    display_image.thumbnail((200, 200))
                    photo = ImageTk.PhotoImage(display_image)
                    photo_ref["photo"] = photo  # Keep reference
                    ref_image_label.configure(image=photo, text="")
                    
                    status_label.configure(text=f"✅ Reference image saved to: {faces_folder}")
                else:
                    ref_image_label.configure(text="❌ Failed to generate.\nIs Stable Diffusion running?")
            
            generate_ref_btn = ctk.CTkButton(
                ref_frame,
                text="Generate Preview",
                command=lambda: threading.Thread(target=generate_reference_image, daemon=True).start(),
                fg_color=COLORS["accent_purple"],
                hover_color=COLORS["accent_cyan"]
            )
            generate_ref_btn.pack(pady=(0, 10))
            
            # --- Scenario Selection ---
            ctk.CTkLabel(
                main_frame,
                text="Select Starting Scenario:",
                font=("Segoe UI", 12, "bold"),
                text_color=COLORS["text_primary"]
            ).pack(anchor="w", padx=10, pady=(15, 5))
            
            scenario_combo = ctk.CTkComboBox(
                main_frame,
                values=[f"{i}: {opt[:60]}..." for i, opt in enumerate(scenario_options)],
                width=850,
                fg_color=COLORS["input_bg"],
                border_color=COLORS["border"],
                text_color=COLORS["text_primary"],
                dropdown_fg_color=COLORS["bg_secondary"],
                dropdown_text_color=COLORS["text_primary"]
            )
            scenario_combo.pack(padx=10, pady=5)
            if scenario_options:
                scenario_combo.set(f"0: {scenario_options[0][:60]}...")
            
            # Scenario preview (scrollable)
            scenario_preview = ctk.CTkTextbox(
                main_frame,
                height=100,
                fg_color=COLORS["input_bg"],
                border_color=COLORS["border"],
                border_width=1,
                text_color=COLORS["text_secondary"],
                wrap="word"
            )
            scenario_preview.pack(fill="x", padx=10, pady=(5, 15))
            if scenario_options:
                scenario_preview.insert("1.0", scenario_options[0])
            scenario_preview.configure(state="disabled")
            
            def on_scenario_change(choice):
                try:
                    idx = int(choice.split(":")[0])
                    if idx < len(scenario_options):
                        scenario_preview.configure(state="normal")
                        scenario_preview.delete("1.0", "end")
                        scenario_preview.insert("1.0", scenario_options[idx])
                        scenario_preview.configure(state="disabled")
                except:
                    pass
            
            scenario_combo.configure(command=on_scenario_change)
            
            # --- Import Button ---
            def do_import():
                # Get selected scenario index
                selected = scenario_combo.get()
                try:
                    scenario_idx = int(selected.split(":")[0])
                except:
                    scenario_idx = 0
                
                # Get edited image prompt
                final_image_prompt = image_prompt_textbox.get("1.0", "end-1c").strip()
                
                # Get source faces folder
                source_folder = ref_image_path["path"] if ref_image_path["path"] else ""
                
                # Convert and save with custom image prompt and source folder
                converted = self.chub_importer.convert(chub_data, scenario_idx)
                # Update with user edits
                char_key = list(converted.keys())[0]
                converted[char_key]["image_prompt"] = final_image_prompt
                if source_folder:
                    converted[char_key]["source_faces_folder"] = source_folder
                
                self.chub_importer.save(converted)
                
                # Refresh character dropdown
                self.refresh_character_list()
                
                dialog.destroy()
                messagebox.showinfo("Success", f"Character '{char_name}' imported successfully!")
            
            btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            btn_frame.pack(pady=20)
            
            ctk.CTkButton(
                btn_frame,
                text="Cancel",
                command=dialog.destroy,
                fg_color=COLORS["input_bg"],
                hover_color=COLORS["hover"],
                border_color=COLORS["border"],
                border_width=1,
                width=150
            ).pack(side="left", padx=20)
            
            ctk.CTkButton(
                btn_frame,
                text="Import Character",
                command=do_import,
                fg_color=COLORS["accent_cyan"],
                hover_color=COLORS["accent_purple"],
                width=150
            ).pack(side="left", padx=20)
            
            # --- Generate Image Prompt with LLM (async) ---
            def generate_image_prompt_async():
                import aiohttp
                import asyncio
                
                description = chub_data.get('description', '')
                
                async def call_llm():
                    system_prompt = """You generate concise image prompts for portrait photos based on character descriptions.
                    
Output format: a short description of the character's appearance for Stable Diffusion, like:
"25yo asian woman with long black hair, glasses, slim build"
"short thick 30yo redhead woman with huge buttocks, tanned skin, trashy tattoos"
"37yo lebanese man with glasses, tan skin, black hair and a beard"

Focus on: age, ethnicity, hair, distinctive features, body type. Keep it under 30 words."""

                    user_prompt = f"""Based on this character description, generate a concise portrait image prompt:

{description}

Generate ONLY the image prompt, nothing else."""

                    # Use OpenRouter
                    from config import OPENROUTER_KEY
                    
                    headers = {
                        "Authorization": f"Bearer {OPENROUTER_KEY}",
                        "Content-Type": "application/json"
                    }
                    
                    payload = {
                        "model": "deepseek/deepseek-chat",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "max_tokens": 100,
                        "temperature": 0.7
                    }
                    
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                "https://openrouter.ai/api/v1/chat/completions",
                                json=payload,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=30)
                            ) as response:
                                if response.status == 200:
                                    r = await response.json()
                                    if 'choices' in r and len(r['choices']) > 0:
                                        return r['choices'][0]['message']['content'].strip().strip('"')
                    except Exception as e:
                        print(f"Error calling LLM: {e}")
                    return None
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(call_llm())
                finally:
                    loop.close()
                
                # Update UI on main thread
                def update_ui():
                    if result:
                        image_prompt_textbox.delete("1.0", "end")
                        image_prompt_textbox.insert("1.0", result)
                        status_label.configure(text="✅ Image prompt generated. You can edit it before importing.")
                    else:
                        image_prompt_textbox.delete("1.0", "end")
                        image_prompt_textbox.insert("1.0", f"{char_name}, detailed portrait")
                        status_label.configure(text="⚠️ LLM failed. Using fallback prompt. You can edit it.")
                
                dialog.after(0, update_ui)
            
            # Start LLM generation in background
            threading.Thread(target=generate_image_prompt_async, daemon=True).start()
            
            # --- Generate Scenarios with LLM if needed ---
            if needs_scenario_generation:
                def generate_scenarios_async():
                    import aiohttp
                    import asyncio
                    
                    description = chub_data.get('description', '')
                    
                    async def call_llm():
                        system_prompt = """You generate starting scenarios for roleplay characters.

Generate 3 different starting scenarios/opening messages for a character. Each should:
- Be 2-4 sentences setting up an initial situation
- Use different settings, moods, or contexts
- Be written from the character's perspective (first person or descriptive)

Format: Return ONLY 3 scenarios, separated by |||

Example:
*She's sitting at the cafe when she spots you walk in* Hey you! Over here!|||*Late at night, your phone buzzes with a text from her* can't sleep... you up?|||*You bump into her at the grocery store* Oh! I didn't expect to see you here..."""

                        user_prompt = f"""Based on this character, generate 3 roleplay starting scenarios:

{description[:2000]}

Generate ONLY the 3 scenarios separated by |||"""

                        from config import OPENROUTER_KEY
                        
                        headers = {
                            "Authorization": f"Bearer {OPENROUTER_KEY}",
                            "Content-Type": "application/json"
                        }
                        
                        payload = {
                            "model": "deepseek/deepseek-chat",
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "max_tokens": 500,
                            "temperature": 0.8
                        }
                        
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.post(
                                    "https://openrouter.ai/api/v1/chat/completions",
                                    json=payload,
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as response:
                                    if response.status == 200:
                                        r = await response.json()
                                        if 'choices' in r and len(r['choices']) > 0:
                                            return r['choices'][0]['message']['content'].strip()
                        except Exception as e:
                            print(f"Error calling LLM for scenarios: {e}")
                        return None
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(call_llm())
                    finally:
                        loop.close()
                    
                    def update_scenarios():
                        nonlocal scenario_options
                        if result:
                            # Parse the scenarios
                            new_scenarios = [s.strip() for s in result.split("|||") if s.strip()]
                            if new_scenarios:
                                scenario_options.clear()
                                scenario_options.extend(new_scenarios)
                                # Update dropdown
                                scenario_combo.configure(values=[f"{i}: {opt[:60]}..." for i, opt in enumerate(scenario_options)])
                                scenario_combo.set(f"0: {scenario_options[0][:60]}...")
                                # Update preview
                                scenario_preview.configure(state="normal")
                                scenario_preview.delete("1.0", "end")
                                scenario_preview.insert("1.0", scenario_options[0])
                                scenario_preview.configure(state="disabled")
                        else:
                            scenario_options[0] = "No scenario - character will respond to your first message"
                            scenario_combo.configure(values=["0: No scenario..."])
                            scenario_combo.set("0: No scenario...")
                    
                    dialog.after(0, update_scenarios)
                
                threading.Thread(target=generate_scenarios_async, daemon=True).start()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Import Error", f"Failed to import character: {e}")

    def refresh_character_list(self):
        """Refresh the character dropdown with imported characters."""
        # Reload imported characters
        from characters import characters as base_chars
        imported = self.chub_importer.load_imported()
        all_chars = {**base_chars, **imported}
        
        # Update the dropdown
        char_list = list(all_chars.keys())
        self.char_combo.configure(values=char_list)
        
        # Update the global characters dict for other parts of the app
        global characters
        characters.update(imported)

    def delete_imported_character(self):
        """Delete an imported character from the launcher."""
        imported = self.chub_importer.list_imported()
        
        if not imported:
            messagebox.showinfo("No Imported Characters", "There are no imported characters to delete.")
            return
        
        # Create delete dialog
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Delete Imported Character")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["bg_primary"])
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 400) // 2
        y = (dialog.winfo_screenheight() - 200) // 2
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            dialog,
            text="Select character to delete:",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=20)
        
        char_var = ctk.StringVar()
        char_combo = ctk.CTkComboBox(
            dialog,
            variable=char_var,
            values=imported,
            width=300,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            dropdown_fg_color=COLORS["bg_secondary"],
            dropdown_text_color=COLORS["text_primary"]
        )
        char_combo.pack(pady=10)
        if imported:
            char_combo.set(imported[0])
        
        def do_delete():
            name = char_var.get()
            if name and messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{name}'?"):
                if self.chub_importer.delete(name):
                    self.refresh_character_list()
                    dialog.destroy()
                    messagebox.showinfo("Deleted", f"Character '{name}' has been deleted.")
                else:
                    messagebox.showerror("Error", f"Failed to delete '{name}'.")
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            fg_color=COLORS["input_bg"],
            hover_color=COLORS["hover"],
            border_color=COLORS["border"],
            border_width=1
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text="Delete",
            command=do_delete,
            fg_color=COLORS["error"],
            hover_color="#dc2626"
        ).pack(side="left", padx=10)

    def on_closing(self):
        self.stop_all_bots()
        self.root.destroy()
        sys.exit(0)

class SplashScreen:
    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        
        self.window = ctk.CTkToplevel(root)
        self.window.overrideredirect(True)  # Frameless
        
        # Load Image
        try:
            logo_path = os.path.join("web", "logo.png")
            if os.path.exists(logo_path):
                image = Image.open(logo_path)
                
                # Get original image size
                original_width, original_height = image.size
                
                # Limit max size to reasonable bounds
                max_size = 400
                if original_width > max_size or original_height > max_size:
                    ratio = min(max_size / original_width, max_size / original_height)
                    display_width = int(original_width * ratio)
                    display_height = int(original_height * ratio)
                else:
                    display_width = original_width
                    display_height = original_height
                
                # Set window size to match image exactly (no background visible)
                self.window.geometry(f"{display_width}x{display_height}")
                
                # Create image that fills the entire window
                self.ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(display_width, display_height))
                self.img_label = ctk.CTkLabel(self.window, image=self.ctk_image, text="")
                self.img_label.place(x=0, y=0, relwidth=1, relheight=1)
                
                # Center window on screen
                screen_width = self.window.winfo_screenwidth()
                screen_height = self.window.winfo_screenheight()
                x = (screen_width - display_width) // 2
                y = (screen_height - display_height) // 2
                self.window.geometry(f"{display_width}x{display_height}+{x}+{y}")
            else:
                # Fallback if image not found
                width, height = 400, 100
                self.window.geometry(f"{width}x{height}")
                self.window.configure(fg_color=COLORS["bg_primary"])
                ctk.CTkLabel(self.window, text="Discord Dreams", font=("Segoe UI", 24, "bold"), text_color=COLORS["accent_cyan"]).pack(expand=True)
                
                # Center fallback window
                screen_width = self.window.winfo_screenwidth()
                screen_height = self.window.winfo_screenheight()
                x = (screen_width - width) // 2
                y = (screen_height - height) // 2
                self.window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception as e:
            print(f"Error loading splash image: {e}")
            # Fallback
            width, height = 400, 100
            self.window.geometry(f"{width}x{height}")
            self.window.configure(fg_color=COLORS["bg_primary"])
            ctk.CTkLabel(self.window, text="Discord Dreams", font=("Segoe UI", 24, "bold"), text_color=COLORS["accent_cyan"]).pack(expand=True)
            
            # Center fallback window
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        self.window.lift()
        self.window.focus_force()
        
        # Auto-close after 1 second
        self.window.after(1000, self.enter_launcher)

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
