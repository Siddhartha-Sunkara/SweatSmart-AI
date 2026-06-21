from pydantic import BaseModel
from typing import Optional


class HealthResponse(BaseModel):
    status: str


class ServiceHealthResponse(BaseModel):
    service: str
    status: str


class ErrorResponse(BaseModel):
    status: str


# =====================================================
# Chat agent responses
# =====================================================

class ChatResponse(BaseModel):
    query: str
    intent: Optional[str] = None
    result: dict
    response: str
    cached: Optional[bool] = None
    cache_distance: Optional[float] = None


# =====================================================
# Workout agent responses
# =====================================================

class WorkoutGenerateResponse(BaseModel):
    workout_plan: dict
