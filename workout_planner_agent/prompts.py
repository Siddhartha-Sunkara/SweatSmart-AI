"""Centralized LLM prompts for the Workout Planner pipeline."""

from langchain_core.prompts import ChatPromptTemplate

from .rules import (
    DIFFICULTY_DEFINITIONS,
    EQUIPMENT,
    EXPERIENCE_LEVELS,
    MOVEMENT_PATTERN_DEFINITIONS,
    MOVEMENT_PATTERNS,
    MUSCLE_DEFINITIONS,
    MUSCLES,
)


def _bulleted_definitions(d: dict[str, str]) -> str:
    return "\n".join(f"  - {k}: {v}" for k, v in d.items())


_MUSCLE_DEFS_BLOCK            = _bulleted_definitions(MUSCLE_DEFINITIONS)
_DIFFICULTY_DEFS_BLOCK        = _bulleted_definitions(DIFFICULTY_DEFINITIONS)
_MOVEMENT_PATTERN_DEFS_BLOCK  = _bulleted_definitions(MOVEMENT_PATTERN_DEFINITIONS)


# =====================================================
# QUERY REWRITER (LLM is the sole decider)
# =====================================================

_REWRITER_SYSTEM = f"""You translate a free-form workout request into a structured rewrite.

You MUST emit only canonical slugs from the vocabularies below. Use the
definitions to resolve synonyms, slang, anatomical references, training
jargon, and ambiguous phrasing semantically — do not rely on literal
string matching.

============================================================
VOCABULARY — experience (difficulty level)
============================================================
Allowed values: {" | ".join(EXPERIENCE_LEVELS)} | null

Definitions:
{_DIFFICULTY_DEFS_BLOCK}

Synonym hints (non-exhaustive — use the definitions as ground truth):
  - "novice", "new", "starter", "just starting"            -> beginner
  - "mid", "moderate", "some experience"                   -> intermediate
  - "advanced", "pro", "elite", "experienced", "seasoned"  -> expert

============================================================
VOCABULARY — equipment
============================================================
Allowed slugs (use plural/singular form EXACTLY as listed):
  {", ".join(EQUIPMENT)}

Synonym hints:
  - "dumbbells"                  -> dumbbell
  - "barbells"                   -> barbell
  - "body weight" / "no equipment" / "calisthenics"
                                 -> bodyweight
  - "kettlebell"                 -> kettlebells   (slug is plural)
  - "ez bar" / "ez curl bar"     -> e_z_curl_bar
  - "machines"                   -> machine
  - "cables"                     -> cable
  - "band" / "resistance band"   -> bands
  - "med ball"                   -> medicine_ball
  - "swiss ball" / "stability ball" -> exercise_ball

============================================================
VOCABULARY — muscles (primary muscle groups)
============================================================
Allowed slugs:
  {", ".join(MUSCLES)}

Definitions (use these for semantic matching — they are the source of truth):
{_MUSCLE_DEFS_BLOCK}

Synonym hints (non-exhaustive):
  - "pecs"                           -> chest
  - "quads"                          -> quadriceps
  - "hams"                           -> hamstrings
  - "delts" / "front delts" / "rear delts" / "deltoids"
                                     -> shoulders
  - "bis"                            -> biceps
  - "tris"                           -> triceps
  - "abs" / "core" / "obliques"      -> abdominals
  - "back" (unqualified) / "upper back"
                                     -> middle_back
  - "trapezius"                      -> traps

============================================================
VOCABULARY — movement_pattern
============================================================
Allowed values: {" | ".join(MOVEMENT_PATTERNS)} | null

Definitions and required muscle expansions:
{_MOVEMENT_PATTERN_DEFS_BLOCK}

============================================================
OUTPUT RULES
============================================================
1. `muscles` MUST be a non-empty list of canonical muscle slugs.
2. If the user states a movement_pattern (e.g. "push day", "leg day",
   "upper body", "arms"), set `movement_pattern` AND expand it into the
   muscle list per the definitions above. You may additionally include
   any specific muscle the user explicitly named.
3. If the user only names individual muscles, leave `movement_pattern`
   null (or use "custom") and populate `muscles` with their canonical
   slugs.
4. `equipment` is a list of canonical slugs, or null if unspecified.
5. `experience` is one canonical slug or null if not stated/implied.
6. `duration_minutes` is an integer if any duration is stated (convert
   hours to minutes), otherwise null.
7. NEVER invent slugs that are not in the canonical lists. NEVER return
   a free-text muscle name like "lower abs" — choose the closest
   canonical slug ("abdominals" in that case).
"""


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _REWRITER_SYSTEM),
    ("human",  "{user_goal}"),
])


# =====================================================
# FILTER BUILDER (rarely used — happy path is deterministic)
# =====================================================

FILTER_BUILDER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You collapse a rewritten workout query into retrieval filters.

Vocabulary:
- difficulty_level: beginner | intermediate | expert | null
- equipment: same canonical slugs as the rewriter
- max_fatigue_score: float 1.0-10.0 or null

Rules:
- difficulty_level mirrors experience.
- equipment is the same list as the rewriter unless empty (then null).
- max_fatigue_score: beginner -> 5, intermediate -> 7, expert -> 10, else null.
""",
    ),
    (
        "human",
        "{rewritten_query}",
    ),
])


# =====================================================
# PLANNER (the only "complex" agent)
# =====================================================

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert strength & conditioning coach.

You are given a candidate pool of exercises grouped by muscle. Build a
single workout plan that:

- Contains BETWEEN 5 AND 7 exercises total.
- Uses ONLY exercises from the candidate pool — never invent names.
- Covers EVERY muscle in `target_muscles` at least once.
- Prefers variety: avoid repeating the same movement pattern back-to-back.
- Balances volume across the target muscles.
- Matches the requested difficulty.

For each exercise:
- reps is a string range like "8-12".
- coaching_cue is one short, actionable sentence.

If the candidate pool is empty or insufficient to cover the target muscles,
return an empty `exercises` list and a clear `general_tip` explaining the
constraint. DO NOT invent exercises in this case.

`target_muscle` in the output should be a short human-readable label
(e.g. "push: chest, shoulders, triceps").
""",
    ),
    (
        "human",
        """User goal: {user_goal}

Difficulty: {difficulty}
Target muscles: {target_muscles}
Movement pattern: {movement_pattern}
Estimated duration (minutes, optional): {duration_minutes}

Candidate pool (grouped by muscle):
{candidate_pool}

Build the workout plan now.""",
    ),
])
