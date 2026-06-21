from pydantic import BaseModel
from typing import Any, Dict, Optional


class ChatRequest(BaseModel):
    user_prompt: str


class WorkoutGenerateRequest(BaseModel):
    user_prompt: str
    filters: Optional[Dict[str, Any]] = None
