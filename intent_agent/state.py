"""State definition for the Intent Router Agent."""

from typing import TypedDict, Literal


IntentLiteral = Literal[
    "workout_generation",
    "exercise_question",
    "injury_modification",
    "progression_plan",
    "nutrition",
    "greeting",
]


class RouterState(TypedDict, total=False):
    query: str
    intent: IntentLiteral
    result: dict
    response: str
