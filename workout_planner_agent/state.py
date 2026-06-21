import operator
from typing import Annotated, TypedDict


class WorkoutState(TypedDict, total=False):
    # =========================================================
    # INPUTS
    # =========================================================
    user_goal:    str
    user_filters: dict          # original caller overrides (optional)

    # =========================================================
    # PIPELINE STAGES
    # =========================================================
    rewritten_query: dict       # RewrittenQuery.model_dump()
    common_filters:  dict       # CommonFilters.model_dump()
    subqueries:      list[dict] # [SubQuery.model_dump(), ...]

    # parallel retrieval — reducer concatenates the per-branch lists
    retrieved_docs:  Annotated[list[dict], operator.add]

    candidate_pool:  dict       # {muscle: [ExerciseDoc.model_dump(), ...]}
    workout_plan:    dict       # WorkoutPlan.model_dump()
