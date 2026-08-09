"""Pydantic schemas for the Intent Router Agent."""

from typing import Literal
from pydantic import BaseModel, Field


class IntentClassification(BaseModel):
    intent: Literal[
        "workout_generation",
        "workout_history",
        "exercise_question",
        "injury_modification",
        "progression_plan",
        "nutrition",
        "greeting",
    ] = Field(description="The user's primary intent")
