# launcher.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import sys
import os
import signal
from datetime import datetime
import threading
from typing import Optional, Dict, Any
from typing import Optional, Dict, Any
import json

# Add parent directory to path so we can import from parent
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from users import list_users
from gamemasters import gamemasters
from config import (
    CLAUDE_MODELS, OPENROUTER_MODELS, DEFAULT_CLAUDE_MODEL,
    OPENAI_IMAGE_MODELS, OPENAI_API_KEY # Import OpenAI models and key
)

class ProcessInfo:
    def __init__(self, process, user, gamemaster):
        self.process = process
        self.user = user
        self.gamemaster = gamemaster
        self.start_time = datetime.now()
        self.last_message_time = None
        self.status = "Running"

class AdventureLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Text Adventure Launcher")
        self.process: Optional[subprocess.Popen] = None
        self.output_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # User selection
        ttk.Label(main_frame, text="Select User:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(main_frame, textvariable=self.user_var)
        self.user_combo['values'] = list_users()
        self.user_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        if self.user_combo['values']:
            self.user_combo.set(self.user_combo['values'][0])
            
        # Game Master selection
        ttk.Label(main_frame, text="Select Game Master:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.gm_var = tk.StringVar()
        self.gm_combo = ttk.Combobox(main_frame, textvariable=self.gm_var)
        self.gm_combo['values'] = list(gamemasters.keys())
        self.gm_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        if self.gm_combo['values']:
            self.gm_combo.set(self.gm_combo['values'][0])
            
        # LLM Settings Frame
        llm_frame = ttk.LabelFrame(main_frame, text="LLM Settings", padding="5")
        llm_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        llm_frame.columnconfigure(1, weight=1)

        # --- LLM Settings ---
        # Main Conversation LLM
        ttk.Label(llm_frame, text="Main Conversation:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        # Provider selection
        provider_frame = ttk.Frame(llm_frame)
        provider_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        provider_frame.columnconfigure(3, weight=1)
        
        ttk.Label(provider_frame, text="Provider:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.main_provider_var = tk.StringVar(value="Anthropic")
        self.main_provider_combo = ttk.Combobox(provider_frame, textvariable=self.main_provider_var, state="readonly", width=15)
        self.main_provider_combo["values"] = ["Anthropic", "OpenRouter"]
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
        ttk.Label(llm_frame, text="Media Generation:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        media_frame = ttk.Frame(llm_frame)
        media_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        media_frame.columnconfigure(3, weight=1)
        
        ttk.Label(media_frame, text="Provider:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        # Determine initial media provider (default to OpenRouter, or OpenAI if key exists and OpenRouter doesn't)
        initial_media_provider = "OpenRouter"
        if OPENAI_API_KEY and not os.getenv('OPENROUTER_KEY'): # Prioritize OpenAI if its key exists and OpenRouter's doesn't
             initial_media_provider = "OpenAI"

        self.media_provider_var = tk.StringVar(value=initial_media_provider)
        self.media_provider_combo = ttk.Combobox(media_frame, textvariable=self.media_provider_var, state="readonly", width=15)
        # Add OpenAI as an option if its API key is configured
        media_providers = ["OpenRouter"]
        if OPENAI_API_KEY:
            media_providers.append("OpenAI")
        self.media_provider_combo["values"] = media_providers
        self.media_provider_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(media_frame, text="Model:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.media_model_var = tk.StringVar()
        self.media_model_combo = ttk.Combobox(media_frame, textvariable=self.media_model_var, state="readonly", width=30)
        self.media_model_combo.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 5))

        # Set initial media model list based on initial provider
        self.update_media_model_list() # Call this to set initial list and default

        # --- Image Generation Service ---
        ttk.Label(llm_frame, text="Image Service:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.image_service_var = tk.StringVar(value="Stable Diffusion (Local)") # Default to SD
        self.image_service_combo = ttk.Combobox(llm_frame, textvariable=self.image_service_var, state="readonly", width=30)

        image_services = ["Stable Diffusion (Local)"]
        if OPENAI_API_KEY:
            image_services.append("OpenAI")
            # Optionally default to OpenAI if key exists?
            # self.image_service_var.set("OpenAI")

        self.image_service_combo["values"] = image_services
        self.image_service_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(0,5))
        if not self.image_service_var.get() in image_services and image_services: # Ensure default is valid
             self.image_service_var.set(image_services[0])


        # Bind events for model list updates
        self.main_provider_combo.bind("<<ComboboxSelected>>", self.on_main_provider_select)
        self.media_provider_combo.bind("<<ComboboxSelected>>", self.on_media_provider_select)
        
        # Output console
        self.console = scrolledtext.ScrolledText(main_frame, height=15, width=60, bg='white')
        self.console.grid(row=4, column=0, columnspan=2, pady=10)
        
        # Configure console tags
        self.console.tag_configure('timestamp', foreground='#666666')  # Gray for timestamps
        self.console.tag_configure('sd_prompt', foreground='#800080')  # Dark purple for SD prompts
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        llm_frame.columnconfigure(1, weight=1)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start Adventure", command=self.start_adventure)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop Adventure", command=self.stop_adventure, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.log("Launcher initialized")

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

    def update_media_model_list(self, event=None): # Added event=None for initial call
        """Update the media generation model list based on selected provider"""
        provider = self.media_provider_var.get()
        if provider == "OpenRouter":
            self.media_model_combo["values"] = [f"{name} ({code})" for name, code in OPENROUTER_MODELS.items()]
            # Set default OpenRouter model (e.g., Cohere)
            default_model = next((f"{name} ({code})" for name, code in OPENROUTER_MODELS.items()
                                if name == "cohere/command-r-plus-04-2024"), None) # Or another suitable default
            if default_model:
                self.media_model_combo.set(default_model)
            elif self.media_model_combo["values"]:
                self.media_model_combo.set(self.media_model_combo["values"][0])
        elif provider == "OpenAI":
            if OPENAI_API_KEY: # Check again if key exists
                self.media_model_combo["values"] = [f"{name} ({code})" for name, code in OPENAI_IMAGE_MODELS.items()]
                # Set default OpenAI model (gpt-image-1)
                default_model = next((f"{name} ({code})" for name, code in OPENAI_IMAGE_MODELS.items()
                                    if name == "gpt-image-1"), None)
                if default_model:
                    self.media_model_combo.set(default_model)
                elif self.media_model_combo["values"]:
                    self.media_model_combo.set(self.media_model_combo["values"][0])
            else:
                # Handle case where OpenAI is selected but key is missing (disable or show message)
                self.media_model_combo["values"] = []
                self.media_model_combo.set("OpenAI API Key Missing")
        else:
             self.media_model_combo["values"] = []
             self.media_model_combo.set("") # Clear if provider unknown

    def on_main_provider_select(self, event):
        """Handle main LLM provider selection"""
        self.update_main_model_list()

    def on_media_provider_select(self, event):
        """Handle media LLM provider selection"""
        self.update_media_model_list() # Pass event implicitly
        
    def log(self, message: str):
        """Add a message to the console with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if "[Stable Diffusion Prompt]" in message:
            self.console.insert(tk.END, f"[{timestamp}] ", 'timestamp')
            self.console.insert(tk.END, f"{message}\n", 'sd_prompt')
        else:
            self.console.insert(tk.END, f"[{timestamp}] ", 'timestamp')
            self.console.insert(tk.END, f"{message}\n")
            
        self.console.see(tk.END)
        
    def start_adventure(self):
        """Start the adventure bot process."""
        if self.process:
            self.log("Adventure already running")
            return
            
        user = self.user_var.get()
        gamemaster = self.gm_var.get()
        
        if not user or not gamemaster:
            self.log("Please select both a user and a game master")
            return
            
        self.log(f"Starting adventure with Game Master '{gamemaster}' for user '{user}'")
        
        # Construct command
        cmd = [
            sys.executable,
            "adventure.py",
            "--user", user,
            "--gamemaster", gamemaster,
            "--main-provider", self.main_provider_var.get(),
            "--main-model", self.main_model_var.get().split(" (")[0], # Extract model name
            "--media-provider", self.media_provider_var.get(), # Provider for prompt generation
            "--media-model", self.media_model_var.get().split(" (")[0], # Model for prompt generation
            "--image-service", self.image_service_var.get() # Add the selected image generation service
        ]
        
        try:
            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',  # Specify UTF-8 encoding
                errors='replace', # Replace characters that can't be decoded
                bufsize=1,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            # Update button states
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.running = True
            
            # Start output thread
            self.output_thread = threading.Thread(target=self.monitor_output)
            self.output_thread.daemon = True
            self.output_thread.start()
            
            self.log("Adventure started successfully")
            
        except Exception as e:
            self.log(f"Error starting adventure: {str(e)}")
            self.process = None
            
    def stop_adventure(self):
        """Stop the adventure bot process."""
        if not self.process:
            return
            
        self.log("Stopping adventure...")
        self.running = False
        
        try:
            if sys.platform == 'win32':
                self.process.terminate()
            else:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        except Exception as e:
            self.log(f"Error stopping process: {str(e)}")
            
        self.process = None
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log("Adventure stopped")
        
    def monitor_output(self):
        """Monitor and log the process output."""
        while self.running and self.process:
            line = self.process.stdout.readline()
            if not line:
                break
            self.log(line.strip())
            
        if self.process:
            self.process.stdout.close()
            self.process.wait()
            
        if self.running:
            self.root.after(0, self.handle_process_end)
            
    def handle_process_end(self):
        """Handle the process ending unexpectedly."""
        self.process = None
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log("Adventure process ended")
        
    def on_closing(self):
        """Handle window closing."""
        if self.process:
            self.stop_adventure()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = AdventureLauncher(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
