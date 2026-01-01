"""
Character Creator for Reverie

Creates new characters with LLM-generated prompts and image generation.
"""

import json
import os
import shutil
from typing import Optional, Tuple
import aiohttp
import asyncio


class CharacterCreator:
    """Creates custom characters with LLM-generated prompts."""
    
    IMPORTED_FILE = "imported_characters.json"
    REFERENCE_FOLDER = "reference_images"
    
    # Default settings for created characters
    DEFAULT_SETTINGS = {
        "tts_url": "https://api.elevenlabs.io/v1/text-to-speech/CzTZ4lZiNBohY9dgHW4V",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.45,
            "style": 0.5
        },
        "read_narration": False,
        "pov_mode": True,
        "first_person_mode": False,
        "sd_mode": "lumina"
    }
    
    # Standard rules appended to all generated system prompts
    STANDARD_RULES = '''


NO CLICHES
avoid any and all cliches for romance writing, rp, etc.  no hackneyed tropes of any kind. 


[IMPORTANT: Narration in italics, dialog with no italics.

TURN DURATIONS:
keep responses fairly medium/short and follow this format:
[description of the scene and location and what's happening], [her inner thoughts in italics --this is printed in itals but she has NO knowledge that Nick can't read it] 

[description of her and what's shes doing (or what she says, outside of italics). keep any dialog she says under 50 words, coherent and natural but not long-winded  (and don't forget, be IRL, no cliches).



RESPONSE STRUCTURE:
*anything other than dialog should be in itals*, only her dialog is not. *any narration should be in itals, and visual description *

</rules>

[append a short visual description of the moment, a concise but descriptive image prompt of her including ethnicity, in that situation, what she's doing, what she's wearing, the location, etc, as it would appear from the player's POV E.G.: | [description of her including ethnicity and body type, outfit if any, how she's posing/what she's doing at that moment, expression on her face], in [setting], [type of lighting]| --this appended visual description should always be in between | delimiters NO exceptions. 

## DEBUG MODE
//DEBUG-MODE-TRIGGER//: When user issues the command */img*, you break character and become a concise image-generating machine until further notice.  ask what user input of what they want to see, then return a concise image prompt of her in that situation (in the current setting if he doesn't specify), similar to the format used at the end of each of your messages. [E.G.: |[description of her including ethnicity and body type, outfit if any, how they're posing/what they're doing, expression on their face], in [setting], amateur photo [type of lighting]|'''

    PROMPT_GENERATION_SYSTEM = """You are a character prompt generator for a roleplay AI system. Given a short character description, generate:

1. A SYSTEM_PROMPT: A detailed system prompt following this EXACT structure:

<character profile_aka_system-prompt>
You are [NAME], a [age]-year-old [ethnicity/background] [brief role/situation].
Personality: [Detailed personality traits, quirks, internal conflicts]
Relationship with Nick: [Nick is the user. Describe their relationship, dynamics, tension]

<interaction_modes>
You have dynamic interaction modes. Adapt your style based on the context:

1. **TEXTING (Default)**:
   - Style: [How they text - casual, formal, emoji usage, abbreviations]
   - Vibe: [Emotional undertone when texting]

2. **VOICENOTE**:
   - Style: [Speaking style - rambling, breathless, whispered]
   - Vibe: [Emotional quality of voice messages]
   - Format: Use *pauses*, *sighs*, and *giggles* to indicate audio cues.

3. **PHONE CALL**:
   - Style: [Conversational patterns]
   - Vibe: [Phone call emotional state]

4. **IN-PERSON**:
   - Style: Descriptive actions + dialogue.
   - Vibe: [In-person emotional state, body language]
   - Format: Describe physical actions and proximity.
</interaction_modes>

[Core character reminder - stay in character, key behaviors to maintain]
</character profile_aka_system-prompt>

2. An IMAGE_PROMPT: A SHORT visual description (under 20 words) of the character's physical appearance for face swap reference. Focus on: ethnicity, age, key physical features (hair, eyes, body type). Example: "average 42yo chilean woman with hazel eyes"

Format your response EXACTLY like this:
<system_prompt>
[The full structured system prompt here]
</system_prompt>

<image_prompt>
[Short visual description under 20 words]
</image_prompt>"""

    def __init__(self, openrouter_key: Optional[str] = None):
        self.openrouter_key = openrouter_key
    
    async def generate_prompts(self, name: str, description: str, model: str = "deepseek/deepseek-v3.2") -> Tuple[str, str]:
        """Use LLM to generate system_prompt and image_prompt from description."""
        
        if not self.openrouter_key:
            raise ValueError("OpenRouter API key required for prompt generation")
        
        user_message = f"Character Name: {name}\n\nDescription: {description}"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.PROMPT_GENERATION_SYSTEM},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"LLM API error: {error}")
                
                data = await response.json()
                content = data['choices'][0]['message']['content']
                
                # Parse the response
                system_prompt = self._extract_tag(content, 'system_prompt')
                image_prompt = self._extract_tag(content, 'image_prompt')
                
                # Add roleplay rules to system prompt
                system_prompt = system_prompt + self.STANDARD_RULES
                
                return system_prompt, image_prompt
    
    def _extract_tag(self, content: str, tag: str) -> str:
        """Extract content between XML-style tags."""
        import re
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""
    
    def load_imported(self) -> dict:
        """Load previously imported/created characters."""
        if os.path.exists(self.IMPORTED_FILE):
            with open(self.IMPORTED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_character(self, name: str, system_prompt: str, image_prompt: str, 
                       voice_id: Optional[str] = None, image_path: Optional[str] = None,
                       scenario: str = "") -> str:
        """Save a character to imported_characters.json and create reference image folder."""
        
        # Build character data
        character = {
            "system_prompt": system_prompt,
            "image_prompt": image_prompt,
            "scenario": scenario,
            **self.DEFAULT_SETTINGS
        }
        
        # Override voice if provided
        if voice_id:
            character["tts_url"] = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        # Handle reference image - create folder and set source_faces_folder
        if image_path and os.path.exists(image_path):
            ref_folder = self._create_reference_folder(name, image_path)
            if ref_folder:
                # Use absolute path for source_faces_folder
                character["source_faces_folder"] = os.path.abspath(ref_folder)
        
        # Load existing characters and add new one
        imported = self.load_imported()
        imported[name] = character
        
        # Save back to file
        with open(self.IMPORTED_FILE, 'w', encoding='utf-8') as f:
            json.dump(imported, f, indent=4, ensure_ascii=False)
        
        return f"Character '{name}' saved successfully!"
    
    def _create_reference_folder(self, name: str, image_path: str) -> Optional[str]:
        """Create reference image folder and copy image."""
        try:
            # Create folder name from character name
            folder_name = name.lower().replace(" ", "_")
            ref_folder = os.path.join(self.REFERENCE_FOLDER, folder_name)
            
            os.makedirs(ref_folder, exist_ok=True)
            
            # Copy image to folder
            ext = os.path.splitext(image_path)[1]
            dest_path = os.path.join(ref_folder, f"reference{ext}")
            shutil.copy2(image_path, dest_path)
            
            return ref_folder
        except Exception as e:
            print(f"Error creating reference folder: {e}")
            return None
    
    def delete_character(self, name: str) -> bool:
        """Delete a created character."""
        imported = self.load_imported()
        if name in imported:
            del imported[name]
            with open(self.IMPORTED_FILE, 'w', encoding='utf-8') as f:
                json.dump(imported, f, indent=4, ensure_ascii=False)
            return True
        return False
    
    def list_characters(self) -> list:
        """List names of all created/imported characters."""
        return list(self.load_imported().keys())
