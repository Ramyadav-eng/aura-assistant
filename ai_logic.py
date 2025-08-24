import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
import io
from prompt_engineering import get_system_prompt

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AURA-AI")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-1.5-flash-latest')
chat_sessions = {}

def get_or_create_chat(session_id="default"):
    if session_id not in chat_sessions:
        logger.info(f"Creating new chat session: {session_id}")
        system_prompt = get_system_prompt()
        chat_sessions[session_id] = model.start_chat(history=[
            {'role': 'user', 'parts': [system_prompt]},
            {'role': 'model', 'parts': ["Understood. I will analyze user goals and provide direct solutions based on the examples provided."]}
        ])
    return chat_sessions[session_id]

async def ask_gemini(prompt: str, image_data: bytes = None, session_id: str = "default") -> str:
    try:
        chat = get_or_create_chat(session_id)
        contents = [prompt, Image.open(io.BytesIO(image_data))] if image_data else [prompt]
        response = await chat.send_message_async(contents)
        return response.text
    except Exception as e:
        logger.error(f"Error in ask_gemini: {e}", exc_info=True)
        return f"An error occurred with the AI service: {str(e)}"

def reset_chat_session(session_id="default"):
    if session_id in chat_sessions:
        del chat_sessions[session_id]