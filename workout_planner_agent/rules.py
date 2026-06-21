"""Canonical vocabularies and definitions for the workout planner.

This module is intentionally data-only. All free-text -> slug decisions are
made by the LLM in ``pipeline/query_rewriter.py`` (see ``REWRITER_PROMPT``
in ``prompts.py``), which is prompted with the definitions below so it has
semantic grounding rather than relying on brittle keyword matching.

Two things still belong here:
  * The canonical slug lists (must mirror the Qdrant payload).
  * ``EXPERIENCE_TO_MAX_FATIGUE`` — a numeric policy, not an NLP rule,
    consumed deterministically by ``pipeline/filter_builder.py``.
"""

from __future__ import annotations


# =====================================================
# CANONICAL SLUG LISTS (must match Qdrant payload)
# =====================================================

MUSCLES: list[str] = [
    "abdominals", "abductors", "adductors", "biceps", "calves",
    "chest", "forearms", "glutes", "hamstrings", "lats",
    "lower_back", "middle_back", "neck", "quadriceps",
    "shoulders", "traps", "triceps",
]

EQUIPMENT: list[str] = [
    "bands", "barbell", "bodyweight", "cable", "dumbbell",
    "e_z_curl_bar", "exercise_ball", "foam_roll", "kettlebells",
    "machine", "medicine_ball", "other",
]

EXPERIENCE_LEVELS: list[str] = ["beginner", "intermediate", "expert"]

MOVEMENT_PATTERNS: list[str] = [
    "push", "pull", "legs", "upper", "lower",
    "arms", "back", "core", "full_body", "custom",
]


# =====================================================
# DEFINITIONS — injected into the rewriter system prompt
# =====================================================

MUSCLE_DEFINITIONS: dict[str, str] = {
    "abdominals":  "Rectus abdominis and obliques. The front 'six-pack' and side trunk muscles. Trained by crunches, planks, leg raises.",
    "abductors":   "Outer hip muscles (e.g. gluteus medius). Move the leg away from the midline. Trained by lateral band walks, cable abductions.",
    "adductors":   "Inner thigh muscles. Pull the leg toward the midline. Trained by adductor machine, sumo stance work, Copenhagen plank.",
    "biceps":      "Front of the upper arm. Flexes the elbow and supinates the forearm. Trained by curls of all kinds.",
    "calves":      "Gastrocnemius and soleus on the back of the lower leg. Trained by standing and seated calf raises.",
    "chest":       "Pectoralis major and minor. Drives horizontal pushing. Trained by bench press, push-ups, flyes, dips.",
    "forearms":    "Wrist flexors and extensors plus grip musculature. Trained by wrist curls, farmer's carries, dead hangs.",
    "glutes":      "Gluteus maximus / medius / minimus. Hip extension and stabilization. Trained by hip thrusts, squats, deadlifts, lunges.",
    "hamstrings":  "Back of the thigh (biceps femoris, semitendinosus, semimembranosus). Flexes the knee and extends the hip. Trained by RDLs, leg curls, good mornings.",
    "lats":        "Latissimus dorsi. Large wing-shaped back muscle. Vertical pulling. Trained by pull-ups, lat pulldowns, pullovers.",
    "lower_back":  "Erector spinae and lumbar musculature. Spinal extension and bracing. Trained by deadlifts, back extensions, good mornings.",
    "middle_back": "Rhomboids and mid-trapezius. Scapular retraction. Trained by rows of all kinds, face pulls, reverse flyes.",
    "neck":        "Cervical flexors and extensors. Trained by neck harness work and isometric holds.",
    "quadriceps":  "Front of the thigh (rectus femoris, vastus lateralis/medialis/intermedius). Extends the knee. Trained by squats, leg presses, leg extensions, lunges.",
    "shoulders":   "Deltoids — front, side, and rear heads. All overhead pressing, lateral raises, and arm-raising. Trained by OHP, lateral raises, rear delt flyes.",
    "traps":       "Upper trapezius. Shrugs and scapular elevation. Trained by shrugs, farmer's carries, upright rows.",
    "triceps":     "Back of the upper arm. Extends the elbow — pressing lockout. Trained by close-grip bench, pushdowns, skullcrushers, dips.",
}

DIFFICULTY_DEFINITIONS: dict[str, str] = {
    "beginner": (
        "Less than ~6 months of consistent training. Needs simple movement "
        "patterns, machines or bodyweight, conservative loading, longer rest, "
        "and low cumulative fatigue. Maps to max_fatigue_score = 5."
    ),
    "intermediate": (
        "Roughly 6 months to 2 years of consistent training. Comfortable with "
        "the main barbell/dumbbell lifts, can handle moderate compound fatigue "
        "and supersets. Maps to max_fatigue_score = 7."
    ),
    "expert": (
        "2+ years of structured training. Can handle high fatigue, advanced "
        "variations, heavy compound work, unilateral and explosive movements. "
        "Maps to max_fatigue_score = 10. Use this for 'advanced', 'pro', or "
        "'elite' lifters."
    ),
}

MOVEMENT_PATTERN_DEFINITIONS: dict[str, str] = {
    "push":      "Horizontal and vertical pushing. Expand to: chest, shoulders, triceps.",
    "pull":      "Vertical and horizontal pulling. Expand to: lats, middle_back, biceps.",
    "legs":      "Lower-body day. Expand to: quadriceps, hamstrings, glutes, calves.",
    "upper":     "Full upper body. Expand to: chest, shoulders, triceps, lats, middle_back, biceps.",
    "lower":     "Full lower body. Expand to: quadriceps, hamstrings, glutes, calves.",
    "arms":      "Isolation arm day. Expand to: biceps, triceps, forearms.",
    "back":      "Back-focused. Expand to: lats, middle_back, lower_back.",
    "core":      "Trunk / midline. Expand to: abdominals.",
    "full_body": "Compound full-body session. Expand to: chest, lats, quadriceps, hamstrings, shoulders, abdominals.",
    "custom":    "User specified an idiosyncratic combination. Use the exact muscles they named — do not force a preset expansion.",
}


# =====================================================
# NUMERIC POLICY (used by filter_builder)
# =====================================================

EXPERIENCE_TO_MAX_FATIGUE: dict[str, float] = {
    "beginner":     5.0,
    "intermediate": 7.0,
    "expert":       10.0,
}
