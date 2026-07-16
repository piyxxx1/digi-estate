from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CallBase(BaseModel):
    caller_name: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    transcript: Optional[str] = None
    ai_response: Optional[str] = None
    call_duration: Optional[int] = Field(None, description="Duration of call in seconds")

class CallCreate(CallBase):
    pass

class CallOut(CallBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
