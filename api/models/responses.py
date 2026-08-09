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


# =====================================================
# Workout history (NL-to-SQL) responses
# =====================================================

class WorkoutHistoryResponse(BaseModel):
    query: str
    user_id: int
    generated_sql: str
    is_valid: bool
    row_count: int
    response: str
