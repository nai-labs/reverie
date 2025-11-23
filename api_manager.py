# api_manager.py
import aiohttp
import json
import logging
from config import (OPENROUTER_URL, ANTHROPIC_URL, OPENROUTER_HEADERS, ANTHROPIC_HEADERS, 
                   OPENROUTER_MODELS, CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL, ANTHROPIC_MAX_TOKENS, 
                   LMSTUDIO_MAX_TOKENS, DEFAULT_LLM, LMSTUDIO_URL, LMSTUDIO_HEADERS, OPENROUTER_MODEL)

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIManager:
    def __init__(self, llm_settings=None):
        # Set defaults first
        # Set defaults first for main conversation LLM
        self.current_llm = DEFAULT_LLM
        self.current_claude_model = DEFAULT_CLAUDE_MODEL
        self.current_openrouter_model = OPENROUTER_MODEL
        self.current_lmstudio_model = None # Assuming LMStudio is not the default

        # Set defaults for media generation LLM (assuming OpenRouter is default)
        self.media_llm_provider = "openrouter"
        self.media_llm_model = "cohere/command-r-plus" # Default media model

        # Override with llm_settings if provided
        if llm_settings:
            # Main LLM settings
            if "main_provider" in llm_settings and "main_model" in llm_settings:
                provider = llm_settings["main_provider"].lower()
                model = llm_settings["main_model"].split(" (")[0] # Extract model name

                if provider in ["anthropic", "openrouter", "lmstudio"]:
                    self.current_llm = provider
                    if provider == "anthropic":
                        self.current_claude_model = model
                    elif provider == "openrouter":
                        self.current_openrouter_model = model
                    elif provider == "lmstudio":
                        self.current_lmstudio_model = model
                else:
                    logger.warning(f"Invalid main provider '{provider}' in llm_settings. Using default '{self.current_llm}'.")

            # Media LLM settings
            if "media_provider" in llm_settings and "media_model" in llm_settings:
                media_provider = llm_settings["media_provider"].lower()
                media_model = llm_settings["media_model"].split(" (")[0] # Extract model name

                # Currently assuming media LLM is always OpenRouter, but structure allows expansion
                if media_provider == "openrouter":
                    self.media_llm_provider = media_provider
                    # TODO: Validate if media_model is actually an OpenRouter model?
                    self.media_llm_model = media_model
                else:
                    logger.warning(f"Invalid media provider '{media_provider}' in llm_settings. Using default '{self.media_llm_provider}'.")

    # This is the correct generate_response method
    async def generate_response(self, message, conversation, system_prompt):
        logger.info(f"APIManager: Generating response using LLM: {self.current_llm}") # Added for debugging
        if self.current_llm == "anthropic":
            response_text = await self.generate_anthropic_response(message, conversation, system_prompt)
        elif self.current_llm == "openrouter":
            response_text = await self.generate_openrouter_response(message, conversation, system_prompt)
        elif self.current_llm == "lmstudio":
            response_text = await self.generate_lmstudio_response(message, conversation, system_prompt)
        else:
            response_text = "Invalid LLM selected."
        return response_text

    async def generate_anthropic_response(self, message, conversation, system_prompt):
        headers = ANTHROPIC_HEADERS.copy()

        # Prepare messages
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation
        ]
        messages.append({"role": "user", "content": message})

        data = {
            "model": self.current_claude_model,
            "messages": messages,
            "system": system_prompt,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "temperature": 0.7,
        }

        # Log the request payload (excluding sensitive information)
        logger.debug(f"Anthropic API Request Payload: {json.dumps({k: v for k, v in data.items() if k != 'messages'}, indent=2)}")
        logger.debug(f"Number of messages in conversation: {len(conversation)}")
        logger.debug(f"Number of messages sent to API: {len(messages)}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ANTHROPIC_URL, json=data, headers=headers) as response:
                    response_json = await response.json()
                    if response.status == 200:
                        if 'content' in response_json:
                            content = response_json['content']
                            response_text = ""
                            for item in content:
                                if item['type'] == 'text':
                                    response_text += item['text']
                            
                            # Log usage information
                            usage = response_json.get('usage', {})
                            input_tokens = usage.get('input_tokens', 0)
                            output_tokens = usage.get('output_tokens', 0)
                            logger.info(f"Input tokens: {input_tokens}")
                            logger.info(f"Output tokens: {output_tokens}")
                            
                            return response_text.strip()
                        else:
                            logger.error("Error: 'content' key not found in the Anthropic API response.")
                    else:
                        logger.error(f"Error: Anthropic API returned status code {response.status}")
                        logger.error(f"Response content: {json.dumps(response_json, indent=2)}")
        except aiohttp.ClientError as e:
            logger.error(f"Network error in generate_anthropic_response: {str(e)}")
            return "I'm having trouble connecting to the Anthropic service right now."
        except Exception as e:
            logger.error(f"Error in generate_anthropic_response: {str(e)}", exc_info=True)
        
        return "I apologize, but I encountered an error while processing your request."

    # --- NEW METHOD START ---
    async def generate_media_llm_response(self, system_prompt, user_prompt, max_tokens=128, temperature=0.3):
        """Generates a response using the configured media LLM."""
        logger.info(f"APIManager: Generating media response using LLM: {self.media_llm_provider} ({self.media_llm_model})")

        # Currently only supports OpenRouter for media LLM
        if self.media_llm_provider != "openrouter":
            logger.error(f"Media LLM provider '{self.media_llm_provider}' is not supported. Only 'openrouter' is implemented.")
            return None # Or raise an error

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        data = {
            "model": self.media_llm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        logger.debug(f"Media LLM (OpenRouter) Request - Model: {self.media_llm_model}")
        logger.debug(f"Media LLM (OpenRouter) Request - Data: {json.dumps(data, indent=2)}")

        try:
            async with aiohttp.ClientSession() as session:
                # Using OPENROUTER_HEADERS defined in config
                async with session.post(OPENROUTER_URL, json=data, headers=OPENROUTER_HEADERS) as response:
                    response_json = await response.json()
                    logger.debug(f"Media LLM (OpenRouter) Response Status: {response.status}")
                    logger.debug(f"Media LLM (OpenRouter) Response: {json.dumps(response_json, indent=2)}")

                    if response.status != 200:
                        logger.error(f"Media LLM (OpenRouter) API Error: {response_json}")
                        return None # Indicate error

                    if 'choices' in response_json and len(response_json['choices']) > 0:
                        response_text = response_json['choices'][0]['message']['content']
                        return response_text.strip()
                    else:
                        logger.error("No choices in Media LLM (OpenRouter) response")
                        return None # Indicate error
        except Exception as e:
            logger.error(f"Exception during Media LLM (OpenRouter) call: {e}", exc_info=True)
            return None # Indicate error
    # --- NEW METHOD END ---

    async def generate_voice_direction(self, text):
        """
        Enhances text with bracketed voice direction tags for ElevenLabs v3.
        Uses the currently selected main LLM.
        """
        logger.info("APIManager: Generating voice direction tags...")
        
        system_prompt = (
            "You are an expert voice director. Your task is to rewrite the following message for a text-to-speech model. "
            "Add bracketed voice direction tags (e.g., [laughter], [sighs], [whispering], [shouting], [clears throat], [giggles]) "
            "to express the emotion and delivery style. "
            "Do not change the core message words significantly, just add the performance tags where appropriate. "
            "Keep it natural."
        )
        
        # Reuse the existing generate_response logic but with a specific system prompt
        # We create a temporary conversation context
        temp_conversation = [] 
        
        # We can use the generic generate_response method
        response = await self.generate_response(text, temp_conversation, system_prompt)
        
        # Clean up response if needed (sometimes models add "Here is the rewritten text:")
        # For now, assume the model follows instructions well enough or we take the whole response.
        return response

    def get_current_llm(self):
        return self.current_llm

    async def generate_openrouter_response(self, message, conversation, system_prompt):
        messages = [
            {"role": "system", "content": system_prompt},
            *[{"role": msg["role"], "content": msg["content"]} for msg in conversation],
            {"role": "user", "content": message}
        ]

        data = {
            "model": self.current_openrouter_model,
            "messages": messages
        }
        
        logger.debug(f"OpenRouter Request - Model: {self.current_openrouter_model}")
        logger.debug(f"OpenRouter Request - Number of messages: {len(messages)}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(OPENROUTER_URL, json=data, headers=OPENROUTER_HEADERS) as response:
                    response_json = await response.json()
                    logger.debug(f"OpenRouter Response Status: {response.status}")
                    logger.debug(f"OpenRouter Response: {json.dumps(response_json, indent=2)}")
                    
                    if response.status != 200:
                        logger.error(f"OpenRouter API Error: {response_json}")
                        return f"Error: {response_json.get('error', {}).get('message', 'Unknown error')}"
                    
                    if 'choices' in response_json and len(response_json['choices']) > 0:
                        response_text = response_json['choices'][0]['message']['content']
                        return response_text
                    else:
                        logger.error("No choices in OpenRouter response")
                        return "No response generated - missing choices in response."
        except aiohttp.ClientError as e:
            logger.error(f"Network error in generate_openrouter_response: {str(e)}")
            return "I'm having trouble connecting to the OpenRouter service right now."
        except Exception as e:
            logger.error(f"Error in generate_openrouter_response: {str(e)}", exc_info=True)
            return "I apologize, but I encountered an error while processing your request."

    async def generate_lmstudio_response(self, message, conversation, system_prompt):
        messages = [
            {"role": "system", "content": system_prompt},
            *[{"role": msg["role"], "content": msg["content"]} for msg in conversation],
            {"role": "user", "content": message}
        ]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(LMSTUDIO_URL, json={
                    "model": self.current_lmstudio_model,
                    "messages": messages,
                    "max_tokens": LMSTUDIO_MAX_TOKENS,
                    "temperature": 0.7,
                }, headers=LMSTUDIO_HEADERS) as response:
                    if response.status != 200:
                        logger.error(f"LMStudio API returned status {response.status}")
                        return "LMStudio service returned an error."
                        
                    response_json = await response.json()
                    if 'choices' in response_json and len(response_json['choices']) > 0:
                        response_text = response_json['choices'][0]['message']['content']
                        return response_text
                    else:
                        return "No response generated from LMStudio."
        except aiohttp.ClientError as e:
            logger.error(f"Network error in generate_lmstudio_response: {str(e)}")
            return "I cannot connect to the local LMStudio server. Is it running?"
        except Exception as e:
            logger.error(f"Error in generate_lmstudio_response: {str(e)}", exc_info=True)
            return "I encountered an error while communicating with LMStudio."

    async def fetch_lmstudio_models(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(LMSTUDIO_URL.replace('chat/completions', 'models'), headers=LMSTUDIO_HEADERS) as response:
                if response.status == 200:
                    models_json = await response.json()
                    return [model['id'] for model in models_json.get('data', [])]
                else:
                    return []

    def switch_llm(self, llm_name):
        if llm_name in ["anthropic", "openrouter", "lmstudio"]:
            self.current_llm = llm_name
            return True
        return False

    def set_lmstudio_model(self, model_name):
        self.current_lmstudio_model = model_name
        self.current_llm = "lmstudio"
        return True

    def get_current_model(self):
        if self.current_llm == "anthropic":
            return self.current_claude_model
        elif self.current_llm == "openrouter":
            return self.current_openrouter_model
        else:
            return self.current_lmstudio_model

    def switch_claude_model(self, model_code):
        for full_name, short_code in CLAUDE_MODELS.items():
            if model_code.lower() == short_code.lower():
                self.current_claude_model = full_name
                self.current_llm = "anthropic"
                return True
        return False

    def switch_openrouter_model(self, model_code):
        for full_name, short_code in OPENROUTER_MODELS.items():
            if model_code.lower() == short_code.lower():
                self.current_openrouter_model = full_name
                self.current_llm = "openrouter"
                return True
        return False

# Removed duplicate get_current_model method that was here
