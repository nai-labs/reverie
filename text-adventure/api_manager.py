# api_manager.py
import aiohttp
import json
import logging
from config import (
    OPENROUTER_URL, ANTHROPIC_URL, OPENROUTER_HEADERS, ANTHROPIC_HEADERS,
    OPENROUTER_MODELS, CLAUDE_MODELS, DEFAULT_CLAUDE_MODEL, ANTHROPIC_MAX_TOKENS,
    DEFAULT_LLM, OPENROUTER_MODEL
)

# Set up logging
logger = logging.getLogger(__name__)

class APIManager:
    def __init__(self, llm_settings=None):
        logger.info("Initializing APIManager with settings: %s", llm_settings)
        llm_settings = llm_settings or {} # Ensure llm_settings is a dict

        # Determine LLM provider
        provider_setting = llm_settings.get("main_provider")
        if provider_setting and provider_setting.lower() in ["anthropic", "openrouter"]:
            self.current_llm = provider_setting.lower()
            logger.info(f"Using main_provider from settings: {self.current_llm}")
        else:
            self.current_llm = DEFAULT_LLM
            logger.info(f"Using default main_provider: {self.current_llm}")

        # Determine Model based on provider
        model_setting = llm_settings.get("main_model")
        if self.current_llm == "anthropic":
            if model_setting:
                 # TODO: Validate if model_setting is a valid Claude model?
                 self.current_claude_model = model_setting # Assume name passed directly now
                 logger.info(f"Using main_model (Claude) from settings: {self.current_claude_model}")
            else:
                 self.current_claude_model = DEFAULT_CLAUDE_MODEL
                 logger.info(f"Using default Claude model: {self.current_claude_model}")
            # Ensure the other provider's default is set too, even if not active
            self.current_openrouter_model = OPENROUTER_MODEL
        elif self.current_llm == "openrouter":
            if model_setting:
                 # TODO: Validate if model_setting is a valid OpenRouter model?
                 self.current_openrouter_model = model_setting # Assume name passed directly now
                 logger.info(f"Using main_model (OpenRouter) from settings: {self.current_openrouter_model}")
            else:
                 self.current_openrouter_model = OPENROUTER_MODEL
                 logger.info(f"Using default OpenRouter model: {self.current_openrouter_model}")
            # Ensure the other provider's default is set too
            self.current_claude_model = DEFAULT_CLAUDE_MODEL
        else:
             # Fallback if current_llm is somehow invalid (shouldn't happen with checks above)
             self.current_claude_model = DEFAULT_CLAUDE_MODEL
             self.current_openrouter_model = OPENROUTER_MODEL
             logger.warning(f"Invalid current_llm '{self.current_llm}', using default models.")

        logger.info(f"APIManager final state - LLM: {self.current_llm}, Model: {self.get_current_model()}")


    async def generate_response(self, message, conversation, system_prompt):
        logger.info(f"Generating response using {self.current_llm} with model {self.get_current_model()}")
        
        if self.current_llm == "anthropic":
            response_text = await self.generate_anthropic_response(message, conversation, system_prompt)
        elif self.current_llm == "openrouter":
            response_text = await self.generate_openrouter_response(message, conversation, system_prompt)
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
        logger.debug(f"Anthropic API Request - Model: {self.current_claude_model}")
        logger.debug(f"Number of messages in conversation: {len(conversation)}")
        logger.debug(f"Number of messages sent to API: {len(messages)}")

        async with aiohttp.ClientSession() as session:
            async with session.post(ANTHROPIC_URL, json=data, headers=headers) as response:
                try:
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
                except Exception as e:
                    logger.error(f"Error in generate_anthropic_response: {str(e)}", exc_info=True)
                
                return "I apologize, but I encountered an error while processing your request."

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

        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_URL, json=data, headers=OPENROUTER_HEADERS) as response:
                response_json = await response.json()
                logger.debug(f"OpenRouter Response Status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"OpenRouter API Error: {response_json}")
                    return f"Error: {response_json.get('error', {}).get('message', 'Unknown error')}"
                
                if 'choices' in response_json and len(response_json['choices']) > 0:
                    response_text = response_json['choices'][0]['message']['content']
                    return response_text
                else:
                    logger.error("No choices in OpenRouter response")
                    return "No response generated - missing choices in response."

    def get_current_llm(self):
        return self.current_llm

    def get_current_model(self):
        if self.current_llm == "anthropic":
            return self.current_claude_model
        else:
            return self.current_openrouter_model

    def switch_claude_model(self, model_code):
        """Switch to a Claude model."""
        for full_name, short_code in CLAUDE_MODELS.items():
            if model_code.lower() == short_code.lower():
                old_model = self.current_claude_model
                self.current_claude_model = full_name
                self.current_llm = "anthropic"
                logger.info(f"Switched Claude model from {old_model} to {full_name}")
                return True
        logger.warning(f"Failed to switch Claude model - invalid code: {model_code}")
        return False

    def switch_openrouter_model(self, model_code):
        """Switch to an OpenRouter model."""
        for full_name, short_code in OPENROUTER_MODELS.items():
            if model_code.lower() == short_code.lower():
                old_model = self.current_openrouter_model
                self.current_openrouter_model = full_name
                self.current_llm = "openrouter"
                logger.info(f"Switched OpenRouter model from {old_model} to {full_name}")
                return True
        logger.warning(f"Failed to switch OpenRouter model - invalid code: {model_code}")
        return False
