from pydantic import BaseModel
from typing import Optional

class ChatResponse(BaseModel):
    response: str

class AudioChatResponse(BaseModel):
    response: str
    transcript: str
    audio_content: Optional[str] = None # For future TTS support
