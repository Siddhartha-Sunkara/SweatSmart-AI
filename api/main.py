from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import health, agent_router
from api.middleware import RequestIDMiddleware, TimeoutMiddleware
from api.config import settings
from api.exceptions import register_exception_handlers
from api.services.agent_service import warm_up_agents, shutdown_executor


@asynccontextmanager
async def lifespan(app: FastAPI):
    await warm_up_agents()
    yield
    await shutdown_executor()


app = FastAPI(lifespan=lifespan)

# Middleware — outermost first (RequestID wraps Timeout)
app.add_middleware(TimeoutMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handlers
register_exception_handlers(app)

@app.get("/")
def root():
    return {"message": "Welcome to Smart SweatSmart API"}


app.include_router(health.router)
app.include_router(agent_router.router)
