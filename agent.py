import os
import asyncio
from dotenv import load_dotenv
from livekit.agents import voice_assistant, vad, stt, tts, llm
from livekit import rtc

# Load environment variables
load_dotenv()

class OpenAILLM(llm.LLM):
    def __init__(self, api_key, model="gpt-4", temperature=0.7, system_prompt=""):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.chat_context = llm.ChatContext()
        if system_prompt:
            self.chat_context.add_message(llm.ChatMessage(role=llm.ChatRole.SYSTEM, content=system_prompt))

    async def chat(self, message: str) -> llm.LLMStream:
        self.chat_context.add_message(llm.ChatMessage(role=llm.ChatRole.USER, content=message))
        response = await self._generate_response()
        self.chat_context.add_message(llm.ChatMessage(role=llm.ChatRole.ASSISTANT, content=response))
        return llm.LLMStream([response])

    async def _generate_response(self) -> str:
        import openai
        client = openai.AsyncOpenAI(api_key=self.api_key)
        
        messages = [
            {"role": msg.role.value.lower(), "content": msg.content}
            for msg in self.chat_context.messages
        ]
        
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        
        return response.choices[0].message.content

async def main():
    # Get LiveKit credentials from environment
    api_key = os.getenv('LIVEKIT_API_KEY')
    api_secret = os.getenv('LIVEKIT_API_SECRET')
    ws_url = os.getenv('LIVEKIT_WS_URL')
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not all([api_key, api_secret, ws_url, openai_api_key]):
        print("Error: Missing required credentials in environment variables")
        return
    
    try:
        # Create components
        voice_detector = vad.WebRTCVAD()
        speech_to_text = stt.OpenAISTT(api_key=openai_api_key)
        language_model = OpenAILLM(
            api_key=openai_api_key,
            model="gpt-4",
            temperature=0.7,
            system_prompt="""
            You are a helpful and friendly AI assistant. You engage in natural conversation,
            providing clear and concise responses. You have a warm, approachable personality
            and aim to make the conversation feel natural and engaging. You keep your responses
            relatively brief and conversational, as this is a voice interaction.
            """
        )
        text_to_speech = tts.OpenAITTS(
            api_key=openai_api_key,
            voice="nova"
        )
        
        # Create room
        room = await rtc.Room.connect(
            url=ws_url,
            token=rtc.AccessToken(api_key, api_secret).with_identity("ai-assistant").to_jwt()
        )
        
        # Create and start the agent
        print("\nStarting voice agent...")
        assistant = voice_assistant.VoiceAssistant(
            vad=voice_detector,
            stt=speech_to_text,
            llm=language_model,
            tts=text_to_speech
        )
        
        assistant.start(room)
        
        # Keep the agent running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down agent...")
        await assistant.aclose()
        await room.disconnect()
    except Exception as e:
        print(f"Error running agent: {e}")

if __name__ == "__main__":
    asyncio.run(main())
