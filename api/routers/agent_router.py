from fastapi import APIRouter
from api.models.requests import ChatRequest, WorkoutGenerateRequest, WorkoutHistoryRequest
from api.models.responses import ChatResponse, WorkoutGenerateResponse, WorkoutHistoryResponse
from api.services.agent_service import chat as chat_service, generate_workout, query_history

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await chat_service(request.user_prompt)


@router.post("/api/workout", response_model=WorkoutGenerateResponse)
async def workout(request: WorkoutGenerateRequest):
    return await generate_workout(request.user_prompt, request.filters)


@router.post("/api/history", response_model=WorkoutHistoryResponse)
async def history(request: WorkoutHistoryRequest):
    return await query_history(request.user_prompt, request.user_id)
