from typing import Optional
from pydantic import BaseModel, Field


# =====================================================
# LEGACY / PUBLIC SCHEMAS (kept for back-compat)
# =====================================================

class ExtractedFilters(BaseModel):
    primary_muscle: Optional[list[str]] = Field(
        None, description="Target muscle groups, e.g. ['chest', 'shoulders']"
    )
    equipment: Optional[list[str]] = Field(
        None, description="Equipment to use, e.g. ['dumbbell', 'barbell']"
    )
    difficulty_level: Optional[str] = Field(
        None, description="Difficulty level: beginner, intermediate, or expert"
    )
    max_fatigue_score: Optional[float] = Field(
        None, description="Maximum fatigue score (1-10)"
    )


class ExerciseBlock(BaseModel):
    exercise_name:  str
    sets:           int
    reps:           str
    rest_seconds:   int
    coaching_cue:   str = Field(description="One concise form tip")


class WorkoutPlan(BaseModel):
    plan_title:                  str
    target_muscle:               str
    difficulty:                  str
    estimated_duration_minutes:  int
    exercises:                   list[ExerciseBlock]
    general_tip:                 str


# =====================================================
# NEW PIPELINE SCHEMAS
# =====================================================

class RewrittenQuery(BaseModel):
    experience: Optional[str] = Field(
        None, description="beginner, intermediate, or expert"
    )
    equipment: Optional[list[str]] = Field(
        None, description="Canonical equipment slugs, e.g. ['dumbbell']"
    )
    muscles: list[str] = Field(
        default_factory=list,
        description="Canonical primary muscle slugs",
    )
    movement_pattern: Optional[str] = Field(
        None,
        description="push / pull / legs / upper / lower / full_body / arms / back / core / custom",
    )
    duration_minutes: Optional[int] = Field(
        None, description="Requested workout duration in minutes"
    )


class CommonFilters(BaseModel):
    difficulty_level:  Optional[str]       = None
    equipment:         Optional[list[str]] = None
    max_fatigue_score: Optional[float]     = None


class SubQuery(BaseModel):
    muscle: str
    query:  str


class ExerciseDoc(BaseModel):
    """Mirror of the Qdrant payload used downstream."""
    exercise_id:       Optional[str]       = None
    exercise_name:     str
    primary_muscles:   list[str]            = Field(default_factory=list)
    secondary_muscles: list[str]            = Field(default_factory=list)
    equipment:         list[str]            = Field(default_factory=list)
    difficulty_level:  Optional[str]       = None
    movement_patterns: list[str]            = Field(default_factory=list)
    fatigue_score:     Optional[float]     = None
    score:             Optional[float]     = None
    document:          Optional[str]       = None


class RetrievalCandidate(BaseModel):
    """Doc tagged with the sub-query muscle that surfaced it."""
    muscle: str
    doc:    ExerciseDoc
