from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    user_message: str
    history: List[ChatMessage]
    user_id: Optional[str] = "default_user"
