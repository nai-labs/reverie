import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from tkinter.ttk import Style # Import Style
import sys
import json
import subprocess
import sys
import os
import signal
import psutil
import re
from datetime import datetime
from PIL import Image, ImageTk
import platform
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# playsound removed due to installation issues - using pygame instead
PLAYSOUND_AVAILABLE = False
import threading
from users import users, list_users
from characters import characters
from config import CLAUDE_MODELS, OPENROUTER_MODELS, DEFAULT_CLAUDE_MODEL
class ConversationWindow:
    def __init__(self, root, process_info, log_file):
        self.window = tk.Toplevel(root)
        self.window.title(f"{process_info.character} - Conversation with {process_info.user}")
        self.window.geometry("800x600")
        
        # Store PhotoImage references to prevent garbage collection
        self.photo_references = []
        
        # Configure the window
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        
        # Create main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Create text widget with custom tags
        self.text = scrolledtext.ScrolledText(
            main_frame, 
            wrap=tk.WORD, 
            font=('Segoe UI', 12, 'bold'),
            background='#1E1E1E',
            foreground='#FFFFFF'
        )
        self.text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure tags for different message types
        self.text.tag_configure('timestamp', foreground='#AAAAAA', font=('Segoe UI', 12))
        self.text.tag_configure('user', foreground='#00B8FF', font=('Segoe UI', 12, 'bold'))
        self.text.tag_configure('bot', foreground='#00FF9C', font=('Segoe UI', 12, 'bold'))
        self.text.tag_configure('italic', font=('Segoe UI', 12, 'italic'))
        
        # Store audio file paths
        self.audio_files = {}
        
        # Create play button image
        play_img = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
        # Draw a simple play triangle
        from PIL import ImageDraw
        draw = ImageDraw.Draw(play_img)
        draw.polygon([(5, 5), (15, 10), (5, 15)], fill='#00FF9C')
        self.play_button_img = ImageTk.PhotoImage(play_img)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Add buttons
        ttk.Button(button_frame, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Copy", command=self.copy_text).pack(side=tk.LEFT, padx=5)
        
        # Auto-refresh checkbutton
        self.auto_refresh = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            button_frame, 
            text="Auto-refresh", 
            variable=self.auto_refresh
        ).pack(side=tk.LEFT, padx=5)
        
        # Store process info and log file
        self.process_info = process_info
        self.log_file = log_file
        
        # Load initial conversation
        self.refresh()
        
        # Start auto-refresh if enabled
        self.check_auto_refresh()
    
    def check_auto_refresh(self):
        """Check if auto-refresh is enabled and refresh if needed"""
        if self.auto_refresh.get():
            self.refresh()
        self.window.after(1000, self.check_auto_refresh)
    
    def format_message_with_italics(self, message, base_tag):
        """Format message with italics for text between asterisks"""
        current_pos = 0
        start_italic = message.find('*')
        
        while start_italic != -1:
            # Add text before the asterisk
            if start_italic > current_pos:
                text = message[current_pos:start_italic]
                self.text.insert(tk.END, text.replace('\\n', '\n'), base_tag)
            
            # Find closing asterisk
            end_italic = message.find('*', start_italic + 1)
            if end_italic == -1:  # No closing asterisk
                # Insert the rest of the text normally
                text = message[start_italic:]
                self.text.insert(tk.END, text.replace('\\n', '\n'), base_tag)
                break
            
            # Insert italicized text (without the asterisks)
            italic_text = message[start_italic + 1:end_italic]
            if italic_text:  # Only if there's text between asterisks
                self.text.insert(tk.END, italic_text.replace('\\n', '\n'), (base_tag, 'italic'))
            
            current_pos = end_italic + 1
            start_italic = message.find('*', current_pos)
        
        # Add any remaining text
        if current_pos < len(message):
            text = message[current_pos:]
            self.text.insert(tk.END, text.replace('\\n', '\n'), base_tag)
    
    def show_full_size_image(self, image_path):
        """Show full size image in a new window"""
        try:
            # Create new window
            image_window = tk.Toplevel(self.window)
            image_window.title("Full Size Image")
            
            # Load full size image
            image = Image.open(image_path)
            photo = ImageTk.PhotoImage(image)
            
            # Keep reference to prevent garbage collection
            image_window.photo = photo
            
            # Create label to display image
            label = ttk.Label(image_window, image=photo)
            label.pack(padx=10, pady=10)
            
            # Add close button
            ttk.Button(image_window, text="Close", command=image_window.destroy).pack(pady=5)
            
            # Center window on screen
            image_window.update_idletasks()
            width = image_window.winfo_width()
            height = image_window.winfo_height()
            x = (image_window.winfo_screenwidth() // 2) - (width // 2)
            y = (image_window.winfo_screenheight() // 2) - (height // 2)
            image_window.geometry(f'+{x}+{y}')
            
        except Exception as e:
            print(f"Error showing full size image: {e}")

    def on_image_click(self, event, image_path):
        """Handle click on thumbnail image"""
        self.show_full_size_image(image_path)

    def load_and_resize_image(self, image_path, max_width=200):
        """Load an image and resize it to fit the window while maintaining aspect ratio"""
        try:
            image = Image.open(image_path)
            
            # Calculate new dimensions
            width, height = image.size
            if width > max_width:
                ratio = max_width / width
                new_width = max_width
                new_height = int(height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image)
            self.photo_references.append(photo)  # Keep reference
            return photo
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            return None

    def play_audio(self, audio_path):
        """Play an audio file in a separate thread using cross-platform method"""
        def play():
            try:
                # Change button color to indicate playing
                self.text.tag_configure('playing', foreground='#FF0000')  # Red color
                current_tags = self.text.tag_names("current")
                for tag in current_tags:
                    if tag.startswith('play_'):
                        self.text.tag_add('playing', f"{self.text.index('current')}-1c")
                
                # Try different audio playback methods based on platform and availability
                audio_played = False
                
                # Method 1: Try winsound on Windows
                if WINSOUND_AVAILABLE and platform.system() == "Windows":
                    try:
                        winsound.PlaySound(audio_path, winsound.SND_FILENAME)
                        audio_played = True
                    except Exception as e:
                        print(f"Winsound failed: {e}")
                
                # Method 2: Try pygame if available
                if not audio_played and PYGAME_AVAILABLE:
                    try:
                        pygame.mixer.music.load(audio_path)
                        pygame.mixer.music.play()
                        # Wait for playback to complete
                        while pygame.mixer.music.get_busy():
                            pygame.time.wait(100)
                        audio_played = True
                    except Exception as e:
                        print(f"Pygame failed: {e}")
                
                # Method 3: Try system commands as last resort
                if not audio_played:
                    try:
                        import shutil
                        if platform.system() == "Windows":
                            # Use Windows Media Player command line
                            os.system(f'powershell -c "(New-Object Media.SoundPlayer \'{audio_path}\').PlaySync();"')
                            audio_played = True
                        elif platform.system() == "Darwin":  # macOS
                            os.system(f'afplay "{audio_path}"')
                            audio_played = True
                        elif platform.system() == "Linux":
                            # Try common Linux audio players
                            for player in ["paplay", "aplay", "play"]:
                                if shutil.which(player):
                                    os.system(f'{player} "{audio_path}"')
                                    audio_played = True
                                    break
                    except Exception as e:
                        print(f"System audio command failed: {e}")
                
                if not audio_played:
                    raise Exception("No audio playback method available. Please ensure pygame is installed or audio system is configured.")
                
                # Reset button color
                self.text.tag_remove('playing', "1.0", tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to play audio: {str(e)}\nPath: {audio_path}")
        
        threading.Thread(target=play, daemon=True).start()

    def refresh(self):
        """Refresh the conversation display"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Clear content and photo references
            self.text.delete('1.0', tk.END)
            self.photo_references.clear()
            
            # Get the output directory path
            output_dir = os.path.dirname(self.log_file)
            
            # Find all messages and TTS files using regex with DOTALL flag
            pattern = r'\[(.*?)\] \*\*(.*?)\*\*: (.*?)(?=\n\[|$)'
            tts_pattern = r'Generated TTS file: (tts_response_\d{8}_\d{6}\.mp3)'
            matches = list(re.finditer(pattern, content, re.DOTALL))
            
            for match in matches:
                timestamp, role, message = match.groups()
                message = message.strip()  # Remove leading/trailing whitespace
                
                # Format timestamp
                self.text.insert(tk.END, f"[{timestamp}] ", 'timestamp')
                
                # Format name and message based on role
                if role.lower() == 'user':
                    self.text.insert(tk.END, f"{self.process_info.user}: ", 'user')
                    self.format_message_with_italics(message, 'user')
                else:
                    # Insert play button if there's a TTS file
                    tts_matches = re.findall(tts_pattern, message)
                    if tts_matches:
                        tts_path = os.path.join(output_dir, tts_matches[-1])  # Use the last TTS file
                        if os.path.exists(tts_path):
                            # Create unique tag for this play button
                            play_tag = f"play_{timestamp}"
                            self.text.image_create(tk.END, image=self.play_button_img, padx=5)
                            self.text.tag_add(play_tag, f"{self.text.index(tk.END)}-1c")
                            self.text.tag_bind(play_tag, '<Button-1>', 
                                             lambda e, path=tts_path: self.play_audio(path))
                    
                    self.text.insert(tk.END, f"{self.process_info.character}: ", 'bot')
                    self.format_message_with_italics(message, 'bot')
                
                # Check for and display any images
                # Look for "Generated selfie: filename.png" in the message
                if "Generated selfie:" in message:
                    # Extract filename from message
                    filename = message.split("Generated selfie:")[1].strip()
                    
                    # Look for the exact image file
                    if filename in os.listdir(output_dir):
                        img_path = os.path.join(output_dir, filename)
                        photo = self.load_and_resize_image(img_path)
                        if photo:
                            self.text.insert(tk.END, "\n")  # New line for image
                            image_index = self.text.index(tk.END)
                            self.text.image_create(tk.END, image=photo)
                            # Bind click event to the image
                            tag_name = f"img_{filename}"
                            self.text.tag_add(tag_name, image_index, self.text.index(tk.END))
                            self.text.tag_bind(tag_name, '<Button-1>', 
                                             lambda e, path=img_path: self.on_image_click(e, path))
                            self.text.insert(tk.END, "\n")  # New line after image
                
                
                # Add double newline after each message for spacing
                self.text.insert(tk.END, "\n\n")
            
            # Scroll to end
            self.text.see(tk.END)
            
        except Exception as e:
            self.text.delete('1.0', tk.END)
            self.text.insert(tk.END, f"Error loading conversation: {str(e)}")
    
    def copy_text(self):
        """Copy selected text to clipboard"""
        try:
            selected_text = self.text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected_text)
        except tk.TclError:  # No selection
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
        self.root.geometry("900x800")  # Reduced height
        self.processes = []  # Track running bot processes
        self.selected_pid = None  # Track selected process
        self.conversation_windows = {}  # Track open conversation windows
        self.update_interval = 1000  # Update process list every second

        # Apply the 'clam' theme
        style = Style(root)
        try:
            style.theme_use('clam')
            print("Applied 'clam' theme.") # Optional: confirm theme application
        except tk.TclError:
            print("Warning: 'clam' theme not available, using default.")

        # Set up window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Create canvas for scrolling
        canvas = tk.Canvas(root)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        
        # Create main frame with padding
        main_frame = ttk.Frame(canvas, padding="10")
        
        # Configure scrolling
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Create window in canvas for main frame
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # Configure grid weights for root
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        
        # Update scroll region when frame size changes
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        main_frame.bind("<Configure>", on_frame_configure)
        
        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # User selection
        ttk.Label(main_frame, text="User:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=(0, 5)) # Added padx, adjusted pady
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(main_frame, textvariable=self.user_var, state="readonly")
        self.user_combo["values"] = list_users()
        self.user_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=(0, 5)) # Added padx, adjusted pady
        self.user_combo.bind("<<ComboboxSelected>>", self.on_user_select)
        
        # Character selection
        ttk.Label(main_frame, text="Character:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # Added padx
        self.char_var = tk.StringVar()
        self.char_combo = ttk.Combobox(main_frame, textvariable=self.char_var, state="readonly")
        self.char_combo["values"] = list(characters.keys())
        self.char_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5) # Added padx
        self.char_combo.bind("<<ComboboxSelected>>", self.on_character_select)
        
        # LLM Settings frame
        llm_frame = ttk.LabelFrame(main_frame, text="LLM Settings", padding="10") # Increased padding
        llm_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10) # Increased pady
        llm_frame.columnconfigure(1, weight=1)
        
        # Main Conversation LLM
        ttk.Label(llm_frame, text="Main Conversation:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5) # Added padx
        
        # Provider selection
        provider_frame = ttk.Frame(llm_frame)
        provider_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5) # Added padx
        provider_frame.columnconfigure(3, weight=1)
        
        ttk.Label(provider_frame, text="Provider:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5)) # Keep existing padx
        self.main_provider_var = tk.StringVar(value="Anthropic")
        self.main_provider_combo = ttk.Combobox(provider_frame, textvariable=self.main_provider_var, state="readonly", width=15)
        self.main_provider_combo["values"] = ["Anthropic", "OpenRouter", "LMStudio"]
        self.main_provider_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(provider_frame, text="Model:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.main_model_var = tk.StringVar()
        self.main_model_combo = ttk.Combobox(provider_frame, textvariable=self.main_model_var, state="readonly", width=30)
        self.main_model_combo.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # Set initial main model list
        self.main_model_combo["values"] = [f"{name} ({code})" for name, code in CLAUDE_MODELS.items()]
        # Find and set the default model
        default_main_model = next((f"{name} ({code})" for name, code in CLAUDE_MODELS.items() 
                                 if name == DEFAULT_CLAUDE_MODEL), None)
        if default_main_model:
            self.main_model_combo.set(default_main_model)
        elif self.main_model_combo["values"]:
            self.main_model_combo.set(self.main_model_combo["values"][0])
        
        # Media Generation LLM
        ttk.Label(llm_frame, text="Media Generation:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # Added padx
        
        media_frame = ttk.Frame(llm_frame)
        media_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5) # Added padx
        media_frame.columnconfigure(3, weight=1)
        
        ttk.Label(media_frame, text="Provider:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5)) # Keep existing padx
        self.media_provider_var = tk.StringVar(value="OpenRouter")
        self.media_provider_combo = ttk.Combobox(media_frame, textvariable=self.media_provider_var, state="readonly", width=15)
        self.media_provider_combo["values"] = ["OpenRouter"]
        self.media_provider_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(media_frame, text="Model:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.media_model_var = tk.StringVar()
        self.media_model_combo = ttk.Combobox(media_frame, textvariable=self.media_model_var, state="readonly", width=30)
        self.media_model_combo.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # Set initial media model list
        self.media_model_combo["values"] = [f"{name} ({code})" for name, code in OPENROUTER_MODELS.items()]
        # Find and set the default model
        default_media_model = next((f"{name} ({code})" for name, code in OPENROUTER_MODELS.items() 
                                  if name == "cohere/command-r-plus-04-2024"), None)
        if default_media_model:
            self.media_model_combo.set(default_media_model)
        elif self.media_model_combo["values"]:
            self.media_model_combo.set(self.media_model_combo["values"][0])
        
        # Bind events for model list updates
        self.main_provider_combo.bind("<<ComboboxSelected>>", self.on_main_provider_select)
        self.media_provider_combo.bind("<<ComboboxSelected>>", self.on_media_provider_select)
        
        # Character parameters frame
        params_frame = ttk.LabelFrame(main_frame, text="Character Parameters", padding="10") # Increased padding
        params_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10) # Increased pady
        params_frame.columnconfigure(1, weight=1)
        
        # System Prompt
        ttk.Label(params_frame, text="System Prompt:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5) # Added padx
        self.system_prompt = scrolledtext.ScrolledText(params_frame, height=3, width=60, wrap=tk.WORD)
        self.system_prompt.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5) # Added padx
        
        # Image Prompt
        ttk.Label(params_frame, text="Image Prompt:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5) # Added padx
        self.image_prompt = scrolledtext.ScrolledText(params_frame, height=1, width=60, wrap=tk.WORD)
        self.image_prompt.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5) # Added padx
        
        # Scenario
        ttk.Label(params_frame, text="Scenario:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5) # Added padx
        self.scenario = scrolledtext.ScrolledText(params_frame, height=1, width=60, wrap=tk.WORD)
        self.scenario.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5) # Added padx
        
        # Voice Settings
        voice_frame = ttk.LabelFrame(params_frame, text="Voice Settings", padding="10") # Increased padding
        voice_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5) # Added padx
        voice_frame.columnconfigure(1, weight=1)
        
        # TTS URL
        ttk.Label(voice_frame, text="TTS URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5) # Added padx
        self.tts_url = ttk.Entry(voice_frame)
        self.tts_url.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5) # Added padx
        
        # Voice Settings (stability, similarity_boost, style)
        settings_frame = ttk.Frame(voice_frame)
        settings_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5) # Added padx
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(3, weight=1)
        settings_frame.columnconfigure(5, weight=1)
        
        # Stability
        ttk.Label(settings_frame, text="Stability:").grid(row=0, column=0, sticky=tk.W)
        self.stability = ttk.Entry(settings_frame, width=10)
        self.stability.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Similarity Boost
        ttk.Label(settings_frame, text="Similarity:").grid(row=0, column=2, sticky=tk.W)
        self.similarity = ttk.Entry(settings_frame, width=10)
        self.similarity.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=5)
        
        # Style
        ttk.Label(settings_frame, text="Style:").grid(row=0, column=4, sticky=tk.W)
        self.style = ttk.Entry(settings_frame, width=10)
        self.style.grid(row=0, column=5, sticky=(tk.W, tk.E), padx=5)
        
        # Process Monitor frame with reduced height
        monitor_frame = ttk.LabelFrame(main_frame, text="Process Monitor", padding="10") # Increased padding
        monitor_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10) # Increased pady
        monitor_frame.columnconfigure(0, weight=1)
        monitor_frame.rowconfigure(0, weight=1)  # Allow treeview to expand
        
        # Create Treeview for process list with reduced height
        self.process_tree = ttk.Treeview(monitor_frame, columns=("pid", "user", "character", "status", "start_time", "last_message"), 
                                       show="headings", height=6)
        
        # Configure columns
        self.process_tree.heading("pid", text="PID")
        self.process_tree.heading("user", text="User")
        self.process_tree.heading("character", text="Character")
        self.process_tree.heading("status", text="Status")
        self.process_tree.heading("start_time", text="Start Time")
        self.process_tree.heading("last_message", text="Last Message")
        
        # Set column widths
        self.process_tree.column("pid", width=70)
        self.process_tree.column("user", width=100)
        self.process_tree.column("character", width=100)
        self.process_tree.column("status", width=80)
        self.process_tree.column("start_time", width=150)
        self.process_tree.column("last_message", width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(monitor_frame, orient=tk.VERTICAL, command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid the Treeview and scrollbar
        self.process_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5) # Added padding
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S), pady=5) # Added pady
        
        # Create context menu for process tree
        self.process_menu = tk.Menu(self.root, tearoff=0)
        self.process_menu.add_command(label="Stop Process", command=self.stop_selected_process)
        
        # Bind events
        self.process_tree.bind("<Double-1>", self.on_process_double_click)
        self.process_tree.bind("<Button-3>", self.show_process_menu)  # Right-click
        self.process_tree.bind("<<TreeviewSelect>>", self.on_process_select)
        
        # Start process monitoring
        self.update_process_list()
        
        # Process control buttons in a more compact layout
        process_buttons = ttk.Frame(monitor_frame)
        process_buttons.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5) # Added padding
        
        # Left-aligned process control buttons
        button_frame_left = ttk.Frame(process_buttons)
        button_frame_left.pack(side=tk.LEFT, expand=True)
        self.stop_selected_button = ttk.Button(button_frame_left, text="Stop Selected", command=self.stop_selected_process, state="disabled")
        self.stop_selected_button.pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame_left, text="Stop All", command=self.stop_all_bots).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame_left, text="Refresh", command=self.update_process_list).pack(side=tk.LEFT, padx=2)
        
        # Bottom buttons in a more compact layout
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10) # Increased pady
        
        # Configure styles
        deploy_style = ttk.Style()
        deploy_style.configure("Deploy.TButton", font=('TkDefaultFont', 10, 'bold'))
        shutdown_style = ttk.Style()
        shutdown_style.configure("Shutdown.TButton", foreground="red")
        
        # Left side - Save Changes
        ttk.Button(bottom_frame, text="Save Changes", command=self.save_changes).pack(side=tk.LEFT, padx=10, pady=5) # Increased padx
        
        # Center - Deploy Bot
        ttk.Button(bottom_frame, text="Deploy Bot", command=self.deploy_bot, style="Deploy.TButton").pack(side=tk.LEFT, padx=10, pady=5, expand=True) # Increased padx
        
        # Right side - Shutdown (in red)
        ttk.Button(bottom_frame, text="Shutdown", command=self.shutdown, style="Shutdown.TButton").pack(side=tk.RIGHT, padx=10, pady=5) # Increased padx
        
        # Set initial values if available
        if self.user_combo["values"]:
            self.user_combo.set(self.user_combo["values"][0])
            self.on_user_select(None)
        
        if self.char_combo["values"]:
            self.char_combo.set(self.char_combo["values"][0])
            self.on_character_select(None)

    def on_user_select(self, event):
        # Update UI based on selected user
        selected_user = self.user_var.get()
        if selected_user in users:
            # Could add user-specific logic here
            pass

    def update_main_model_list(self):
        """Update the main conversation model list based on selected provider"""
        provider = self.main_provider_var.get()
        if provider == "Anthropic":
            self.main_model_combo["values"] = [f"{name} ({code})" for name, code in CLAUDE_MODELS.items()]
            if self.main_model_combo["values"]:
                self.main_model_combo.set(self.main_model_combo["values"][0])
        elif provider == "OpenRouter":
            self.main_model_combo["values"] = [f"{name} ({code})" for name, code in OPENROUTER_MODELS.items()]
            if self.main_model_combo["values"]:
                self.main_model_combo.set(self.main_model_combo["values"][0])
        elif provider == "LMStudio":
            # For LMStudio, we could add a refresh button that queries available models
            self.main_model_combo["values"] = ["default"]
            self.main_model_combo.set("default")

    def update_media_model_list(self):
        """Update the media generation model list"""
        if self.media_provider_var.get() == "OpenRouter":
            self.media_model_combo["values"] = [f"{name} ({code})" for name, code in OPENROUTER_MODELS.items()]
            # Set default to cohere/command-r-plus
            default_model = next((f"{name} ({code})" for name, code in OPENROUTER_MODELS.items() 
                                if name == "cohere/command-r-plus"), None)
            if default_model:
                self.media_model_combo.set(default_model)
            elif self.media_model_combo["values"]:
                self.media_model_combo.set(self.media_model_combo["values"][0])

    def on_main_provider_select(self, event):
        """Handle main LLM provider selection"""
        self.update_main_model_list()

    def on_media_provider_select(self, event):
        """Handle media LLM provider selection"""
        self.update_media_model_list()

    def on_character_select(self, event):
        # Update UI based on selected character
        selected_char = self.char_var.get()
        if selected_char in characters:
            char_data = characters[selected_char]
            
            # Update LLM settings
            llm_settings = char_data.get("llm_settings", {})
            
            # Set main conversation provider and model
            main_provider = llm_settings.get("main_provider", "Anthropic")
            self.main_provider_var.set(main_provider)
            self.update_main_model_list()
            
            # Set main model if it exists in character data
            if "main_model" in llm_settings:
                self.main_model_var.set(llm_settings["main_model"])
            # Otherwise set default based on provider
            elif main_provider == "Anthropic":
                default_model = next((f"{name} ({code})" for name, code in CLAUDE_MODELS.items() 
                                   if name == DEFAULT_CLAUDE_MODEL), None)
                if default_model:
                    self.main_model_var.set(default_model)
            
            # Set media generation provider and model
            media_provider = llm_settings.get("media_provider", "OpenRouter")
            self.media_provider_var.set(media_provider)
            self.update_media_model_list()
            
            # Set media model if it exists in character data
            if "media_model" in llm_settings:
                self.media_model_var.set(llm_settings["media_model"])
            # Otherwise set default OpenRouter model
            elif media_provider == "OpenRouter":
                default_model = next((f"{name} ({code})" for name, code in OPENROUTER_MODELS.items() 
                                   if name == "cohere/command-r-plus-04-2024"), None)
                if default_model:
                    self.media_model_var.set(default_model)
            
            # Update system prompt
            self.system_prompt.delete(1.0, tk.END)
            self.system_prompt.insert(tk.END, char_data.get("system_prompt", ""))
            
            # Update image prompt
            self.image_prompt.delete(1.0, tk.END)
            self.image_prompt.insert(tk.END, char_data.get("image_prompt", ""))
            
            # Update scenario
            self.scenario.delete(1.0, tk.END)
            self.scenario.insert(tk.END, char_data.get("scenario", ""))
            
            # Update TTS URL
            self.tts_url.delete(0, tk.END)
            self.tts_url.insert(0, char_data.get("tts_url", ""))
            
            # Update voice settings
            voice_settings = char_data.get("voice_settings", {})
            self.stability.delete(0, tk.END)
            self.stability.insert(0, str(voice_settings.get("stability", 0.4)))
            
            self.similarity.delete(0, tk.END)
            self.similarity.insert(0, str(voice_settings.get("similarity_boost", 0.45)))
            
            self.style.delete(0, tk.END)
            self.style.insert(0, str(voice_settings.get("style", 0.5)))

    def save_changes(self):
        selected_char = self.char_var.get()
        if selected_char:
            # Get the scenario text and LLM settings
            scenario_text = self.scenario.get(1.0, tk.END.strip())
            
            # Build the update dictionary
            update_data = {
                "system_prompt": self.system_prompt.get(1.0, tk.END.strip()),
                "image_prompt": self.image_prompt.get(1.0, tk.END.strip()),
                "tts_url": self.tts_url.get(),
                "voice_settings": {
                    "stability": float(self.stability.get()),
                    "similarity_boost": float(self.similarity.get()),
                    "style": float(self.style.get())
                },
                "llm_settings": {
                    "main_provider": self.main_provider_var.get(),
                    "main_model": self.main_model_var.get(),
                    "media_provider": self.media_provider_var.get(),
                    "media_model": self.media_model_var.get()
                }
            }
            
            # Only add scenario if it's not empty
            if scenario_text:
                update_data["scenario"] = scenario_text
            
            # Update character data
            characters[selected_char].update(update_data)
            
            # Save to characters.py
            try:
                with open("characters.py", "w", encoding="utf-8") as f:
                    f.write("characters = " + json.dumps(characters, indent=4, ensure_ascii=False))
                messagebox.showinfo("Success", "Character changes saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save changes: {str(e)}")

    def deploy_bot(self):
        selected_user = self.user_var.get()
        selected_char = self.char_var.get()
        
        if not selected_user or not selected_char:
            messagebox.showerror("Error", "Please select both a user and a character")
            return
        
        try:
            # Get the appropriate Python executable for the current platform
            def get_python_executable():
                import shutil
                
                # Check if current sys.executable is valid and accessible
                if os.path.exists(sys.executable) and os.access(sys.executable, os.X_OK):
                    # If sys.executable works and matches the platform, use it
                    if ((platform.system() == "Windows" and sys.executable.endswith('.exe')) or
                        (platform.system() != "Windows" and not sys.executable.endswith('.exe'))):
                        return sys.executable
                
                # If we're on Windows, try to find appropriate Python
                if platform.system() == "Windows" or os.name == 'nt':
                    # First try local venv
                    local_python = os.path.join("venv", "Scripts", "python.exe")
                    if os.path.exists(local_python):
                        return local_python
                    
                    # Try to find python.exe in PATH
                    python_exe = shutil.which("python.exe")
                    if python_exe:
                        return python_exe
                    
                    # Fall back to just "python"
                    return "python"
                else:
                    # For Unix-like systems (WSL, macOS, Linux)
                    local_python = os.path.join("venv", "bin", "python")
                    if os.path.exists(local_python):
                        return local_python
                    
                    # Try python3 first, then python
                    for python_name in ["python3", "python"]:
                        python_exe = shutil.which(python_name)
                        if python_exe:
                            return python_exe
                    
                    # Last resort: use sys.executable even if it seems wrong
                    return sys.executable
            
            python_exe = get_python_executable()
            
            print(f"Debug: Using Python executable: {python_exe}")
            print(f"Debug: Platform: {platform.system()}, os.name: {os.name}")
            
            # Launch the bot as a subprocess with its own process group
            cmd = [
                python_exe, 
                "next.py", 
                "--user", selected_user, 
                "--character", selected_char,
                "--main-provider", self.main_provider_var.get(),
                "--main-model", self.main_model_var.get().split(" (")[0],  # Remove the shortcode in parentheses
                "--media-provider", self.media_provider_var.get(),
                "--media-model", self.media_model_var.get().split(" (")[0]  # Remove the shortcode in parentheses
            ]
            if os.name == 'nt':  # Windows
                process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:  # Unix
                process = subprocess.Popen(cmd, preexec_fn=os.setsid)
            
            # Create ProcessInfo object and add to list
            process_info = ProcessInfo(process, selected_user, selected_char)
            self.processes.append(process_info)
            
            # Update process list immediately
            self.update_process_list()
            
            messagebox.showinfo("Success", f"Bot deployed with user '{selected_user}' and character '{selected_char}'")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to deploy bot: {str(e)}")

    def stop_process(self, process_info):
        """Stop a single bot process"""
        try:
            if os.name == 'nt':  # Windows
                # Get the process and all its children
                parent = psutil.Process(process_info.process.pid)
                children = parent.children(recursive=True)
                
                # Terminate children first
                for child in children:
                    child.terminate()
                
                # Terminate parent
                parent.terminate()
                
                # Wait for processes to terminate
                gone, alive = psutil.wait_procs([parent] + children, timeout=3)
                
                # Force kill if still alive
                for p in alive:
                    p.kill()
            else:  # Unix
                os.killpg(os.getpgid(process_info.process.pid), signal.SIGTERM)
            
            process_info.status = "Stopped"
            self.processes.remove(process_info)
            return True
        except (psutil.NoSuchProcess, ProcessLookupError):
            # Process already terminated
            self.processes.remove(process_info)
            return True
        except Exception as e:
            print(f"Error stopping process: {e}")
            return False

    def stop_all_bots(self):
        """Stop all running bot processes"""
        success = True
        for process_info in self.processes[:]:  # Create a copy of the list to iterate
            if not self.stop_process(process_info):
                success = False
        
        if not self.processes and success:
            messagebox.showinfo("Success", "All bots stopped")
        else:
            messagebox.showwarning("Warning", "Some bots could not be stopped")

    def update_process_list(self):
        """Update the process monitor display"""
        # Store currently selected item
        selected_pid = self.selected_pid
        
        # Clear current items
        for item in self.process_tree.get_children():
            self.process_tree.delete(item)
        
        # Update process statuses and add to tree
        for process_info in self.processes[:]:
            try:
                # Check if process is still running
                if process_info.process.poll() is not None:
                    process_info.status = "Stopped"
                    self.processes.remove(process_info)
                    continue
                
                # Check for last message time
                output_dir = os.path.join("output")
                if os.path.exists(output_dir):
                    subdirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
                    if subdirs:
                        latest_dir = max(subdirs, key=lambda d: os.path.getctime(os.path.join(output_dir, d)))
                        log_file = os.path.join(output_dir, latest_dir, f"{latest_dir}.txt")
                        if os.path.exists(log_file):
                            process_info.last_message_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                
                # Add to tree
                item_id = self.process_tree.insert("", "end", values=(
                    process_info.process.pid,
                    process_info.user,
                    process_info.character,
                    process_info.status,
                    process_info.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    process_info.last_message_time.strftime("%Y-%m-%d %H:%M:%S") if process_info.last_message_time else "No messages"
                ))
                
                # Restore selection if this was the selected item
                if process_info.process.pid == selected_pid:
                    self.process_tree.selection_set(item_id)
                
            except (psutil.NoSuchProcess, ProcessLookupError):
                process_info.status = "Stopped"
                self.processes.remove(process_info)
        
        # Schedule next update
        self.root.after(self.update_interval, self.update_process_list)

    def on_process_double_click(self, event):
        """Handle double-click on process in tree"""
        item = self.process_tree.selection()[0]
        pid = self.process_tree.item(item)["values"][0]
        
        # Find process info
        process_info = next((p for p in self.processes if p.process.pid == pid), None)
        if process_info:
            # Check if window already exists
            if pid in self.conversation_windows:
                # Bring existing window to front
                self.conversation_windows[pid].window.lift()
                return
            
            # Find the log file
            if process_info.last_message_time:  # If there are messages
                log_file = None
                output_dir = os.path.join("output")
                if os.path.exists(output_dir):
                    subdirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
                    if subdirs:
                        latest_dir = max(subdirs, key=lambda d: os.path.getctime(os.path.join(output_dir, d)))
                        log_file = os.path.join(output_dir, latest_dir, f"{latest_dir}.txt")
                
                if log_file and os.path.exists(log_file):
                    # Create and store conversation window
                    window = ConversationWindow(self.root, process_info, log_file)
                    self.conversation_windows[pid] = window
                    
                    # Remove from tracking when window is closed
                    window.window.protocol("WM_DELETE_WINDOW", 
                        lambda p=pid: self.on_conversation_window_close(p))
                else:
                    messagebox.showwarning("Warning", "No conversation log file found.")
            else:
                messagebox.showinfo("Info", "No messages yet for this process.")

    def on_conversation_window_close(self, pid):
        """Handle conversation window closing"""
        if pid in self.conversation_windows:
            self.conversation_windows[pid].window.destroy()
            del self.conversation_windows[pid]

    def show_process_menu(self, event):
        """Show context menu on right-click"""
        item = self.process_tree.identify_row(event.y)
        if item:
            self.process_tree.selection_set(item)
            self.process_menu.post(event.x_root, event.y_root)

    def on_process_select(self, event):
        """Handle process selection"""
        selected = self.process_tree.selection()
        if selected:
            item = selected[0]
            pid = self.process_tree.item(item)["values"][0]
            self.selected_pid = pid
            self.stop_selected_button.configure(state="normal")
        else:
            self.selected_pid = None
            self.stop_selected_button.configure(state="disabled")

    def stop_selected_process(self):
        """Stop the selected process"""
        selected = self.process_tree.selection()
        if not selected:
            return
        
        item = selected[0]
        pid = self.process_tree.item(item)["values"][0]
        process_info = next((p for p in self.processes if p.process.pid == pid), None)
        
        if process_info:
            if self.stop_process(process_info):
                messagebox.showinfo("Success", f"Process {pid} stopped")
            else:
                messagebox.showerror("Error", f"Failed to stop process {pid}")
            self.update_process_list()

    def shutdown(self):
        """Shutdown the launcher and all bot processes"""
        if messagebox.askyesno("Confirm Shutdown", "Are you sure you want to shut down?\nThis will stop all running bots."):
            try:
                self.stop_all_bots()
            finally:
                self.root.destroy()
                sys.exit(0)

    def on_closing(self):
        """Handle window closing"""
        try:
            self.stop_all_bots()
        finally:
            self.root.destroy()

def main():
    try:
        root = tk.Tk()
        app = BotLauncher(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if 'app' in locals():
            app.stop_all_bots()

if __name__ == "__main__":
    main()
