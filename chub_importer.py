"""
Chub.ai Character Card Importer for Reverie

Converts Chub card JSON files to Reverie character format.
"""

import json
import os
import re
from typing import Optional


class ChubImporter:
    """Imports and converts Chub.ai character cards to Reverie format."""
    
    IMPORTED_FILE = "imported_characters.json"
    
    # Default settings for imported characters
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
    
    SELFIE_TRIGGER = '''

//SELFIE-MODE-TRIGGER//: When user issues the command */selfies*, you become a concise selfie-generating machine. Ask what they want to see, then return a concise image prompt of the character in that situation. [E.G.: |[description of character posing/doing something], in [setting], amateur photo|]'''

    ROLEPLAY_RULES = '''

## RULES
- Responses should be short flavor text and dialog, not long-winded.
- Narration and any game engine message always in italics.
- Dialog always not in italics. everything else italics.
- Append after each response, a short visual description of what the user sees from his POV, in italics in between | delimiters e.g.:
	"*|POV looking at a vast mountain landscape, with a shiny golden path that winds through the trees up the mountains to a glowing peak with blue sparks and fire.|*"
	"*|POV, a hallway in a hospital in Boston MA. there are wooden doors on either side of the hallway, and at the end there is a metal gate, with a padlock hanging from it|*"
	"*|POV image looking at dingy hotel room, with an unmade bed and harsh flourescent lighting. On the coffee table, a cat is sleeping|*"
	"*|candid POV shot of a dark, dingy hotel room. Unmade bed, harsh fluorescent lighting. A sexy 24yo Chinese girl is stretching on the bed|*"
	"*|POV shot, a nerdy 18yo american girl with glasses and pigtails, looking nervous and unsure, wearing an oversize hoodie and yoga pants, sitting on a couch in a messy dorm room.|*"
	"*|POV shot, closeup of a sexy 26yo latina girl with braids and a choker, extreme closeup looking into viewers eyes, sultry|*"
- Always include the room/setting in the visual description.
	- Always include what the character is wearing for continuity.
- When making a series of visual descriptions in the same setting and/or same character, keep the visual description you give across turns consistent, changing only what you need to change, so imagery is consistent yet advances with what's happening as the story goes on (persistent outfits unless she changes/takes them off, etc).
- Every 3 or 4 turns, something unexpected happens that the user wouldn't predict.'''

    def parse(self, json_path: str) -> dict:
        """Parse a Chub card JSON file."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both raw data and spec_v2 wrapper
        if 'data' in data:
            return data['data']
        return data
    
    def _replace_placeholders(self, text: str, char_name: str) -> str:
        """Replace Chub placeholders with Reverie equivalents."""
        if not text:
            return ""
        
        # Replace character placeholders
        text = re.sub(r'\{\{char\}\}', char_name, text, flags=re.IGNORECASE)
        text = re.sub(r'\{char\}', char_name, text, flags=re.IGNORECASE)
        
        # Replace user placeholders
        text = re.sub(r'\{\{user\}\}', 'you', text, flags=re.IGNORECASE)
        text = re.sub(r'\{user\}', 'you', text, flags=re.IGNORECASE)
        
        # Remove SillyTavern-specific tags
        text = text.replace('<START>', '')
        text = text.replace('###', '')
        
        return text.strip()
    
    def _extract_image_prompt(self, description: str, name: str) -> str:
        """Extract a visual description from the character description."""
        # Look for appearance-related keywords and extract
        # This is a simple heuristic - just use the name and basic descriptors
        lines = description.split('\n')
        for line in lines:
            lower = line.lower()
            if any(word in lower for word in ['hair', 'eyes', 'body', 'skin', 'tall', 'short']):
                # Found an appearance line, use it
                clean = self._replace_placeholders(line, name)
                if len(clean) < 200:
                    return clean
        
        # Fallback: just use the name
        return f"{name}, detailed portrait"
    
    def convert(self, chub_data: dict, scenario_index: int = 0) -> dict:
        """Convert Chub card data to Reverie character format."""
        name = chub_data.get('name', 'Imported Character')
        
        # Build system prompt from multiple fields
        parts = []
        
        # Main description/persona
        if chub_data.get('description'):
            parts.append(self._replace_placeholders(chub_data['description'], name))
        
        if chub_data.get('personality'):
            parts.append(self._replace_placeholders(chub_data['personality'], name))
        
        # Add example dialogue if present
        if chub_data.get('mes_example'):
            examples = self._replace_placeholders(chub_data['mes_example'], name)
            parts.append(f"\n<example_dialogue>\n{examples}\n</example_dialogue>")
        
        # Add scenario instructions (OOC rules)
        scenario_rules = chub_data.get('scenario', '')
        if scenario_rules and '[OOC' in scenario_rules:
            rules = self._replace_placeholders(scenario_rules, name)
            parts.append(f"\n<rules>\n{rules}\n</rules>")
        
        # Add system prompt rules
        if chub_data.get('system_prompt'):
            sys_rules = self._replace_placeholders(chub_data['system_prompt'], name)
            parts.append(f"\n{sys_rules}")
        
        # Add post-history instructions
        if chub_data.get('post_history_instructions'):
            post = self._replace_placeholders(chub_data['post_history_instructions'], name)
            parts.append(f"\n{post}")
        
        # Add selfie trigger and roleplay rules
        parts.append(self.SELFIE_TRIGGER)
        parts.append(self.ROLEPLAY_RULES)
        
        system_prompt = '\n\n'.join(parts)
        
        # Get scenario (first message or alternate greeting)
        scenario = ""
        if scenario_index == 0 and chub_data.get('first_mes'):
            scenario = self._replace_placeholders(chub_data['first_mes'], name)
        elif chub_data.get('alternate_greetings') and len(chub_data['alternate_greetings']) > scenario_index - 1:
            idx = scenario_index - 1 if scenario_index > 0 else 0
            if idx < len(chub_data['alternate_greetings']):
                scenario = self._replace_placeholders(chub_data['alternate_greetings'][idx], name)
        
        # Build the character dict
        character = {
            "system_prompt": system_prompt,
            "image_prompt": self._extract_image_prompt(chub_data.get('description', ''), name),
            "scenario": scenario,
            **self.DEFAULT_SETTINGS
        }
        
        return {name: character}
    
    def get_scenario_options(self, chub_data: dict) -> list:
        """Get list of available scenarios from a Chub card (full text)."""
        options = []
        
        if chub_data.get('first_mes'):
            options.append(chub_data['first_mes'])
        
        for greeting in chub_data.get('alternate_greetings', []):
            options.append(greeting)
        
        return options if options else ["No scenarios available"]
    
    def load_imported(self) -> dict:
        """Load previously imported characters."""
        if os.path.exists(self.IMPORTED_FILE):
            with open(self.IMPORTED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save(self, character: dict):
        """Save a character to the imported characters file."""
        existing = self.load_imported()
        existing.update(character)
        
        with open(self.IMPORTED_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    
    def delete(self, name: str) -> bool:
        """Delete an imported character by name."""
        existing = self.load_imported()
        if name in existing:
            del existing[name]
            with open(self.IMPORTED_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            return True
        return False
    
    def list_imported(self) -> list:
        """List names of all imported characters."""
        return list(self.load_imported().keys())

    def update_all_with_rules(self) -> int:
        """Update all existing imported characters with the roleplay rules."""
        existing = self.load_imported()
        updated = 0
        
        for name, char_data in existing.items():
            system_prompt = char_data.get("system_prompt", "")
            
            # Check if rules already exist
            if "## RULES" not in system_prompt:
                # Add the rules
                char_data["system_prompt"] = system_prompt + self.ROLEPLAY_RULES
                updated += 1
                print(f"[ChubImporter] Added rules to: {name}")
        
        if updated > 0:
            with open(self.IMPORTED_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        
        return updated
