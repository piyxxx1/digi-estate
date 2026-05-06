import os
from google import genai
from google.genai import types
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from constants import ASSISTANT_CONTEXT
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Configure Gemini Client
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY not found in environment variables")

client = genai.Client(api_key=api_key)
MODEL_ID = "gemini-2.5-flash"

class ChatMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    user_message: str
    history: List[ChatMessage]

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        # Prepare history for the new Google GenAI SDK
        # Gemini history MUST start with 'user' and alternate roles
        first_user_index = -1
        for i, msg in enumerate(request.history):
            if msg.role == 'user':
                first_user_index = i
                break
        
        valid_history = []
        if first_user_index != -1:
            for msg in request.history[first_user_index:]:
                valid_history.append(
                    types.Content(
                        role="user" if msg.role == "user" else "model",
                        parts=[types.Part(text=msg.text)]
                    )
                )
        
        # Ensure alternating roles and correct end (last must be model if we are about to send a user message)
        if valid_history and valid_history[-1].role == "user":
            valid_history.pop()

        # Create a chat session with system instruction and history
        chat_session = client.chats.create(
            model=MODEL_ID,
            history=valid_history,
            config=types.GenerateContentConfig(
                system_instruction=ASSISTANT_CONTEXT
            )
        )
        
        response = chat_session.send_message(request.user_message)
        
        return {"response": response.text}
        
    except Exception as e:
        print(f"Gemini Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
