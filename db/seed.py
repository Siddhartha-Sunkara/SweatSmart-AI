"""Seed the workout-log database with realistic training data.

Usage:
    python -m db.seed          # create tables + seed (skip if data exists)
    python -m db.seed --reset  # drop all tables, recreate, and seed
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta
from typing import NamedTuple

from db.engine import Base, SessionLocal, engine
from db.models import ExerciseSet, SessionExercise, User, WorkoutSession

# ── Reproducible output ──────────────────────────────────────────────
random.seed(42)

# ── Exercise catalog ─────────────────────────────────────────────────
# Each entry: (name, primary_muscle, secondary_muscles, equipment,
#              type)
#   type: "compound" | "isolation" | "bodyweight"
#   This drives set/rep/weight generation.


class ExDef(NamedTuple):
    name: str
    primary: str
    secondary: str  # comma-separated slugs or ""
    equipment: str
    kind: str  # compound | isolation | bodyweight


EXERCISES: dict[str, list[ExDef]] = {
    # ── Push ──────────────────────────────────────────────────────
    "push": [
        ExDef("Barbell Bench Press", "chest", "triceps,shoulders", "barbell", "compound"),
        ExDef("Incline Dumbbell Press", "chest", "triceps,shoulders", "dumbbell", "compound"),
        ExDef("Dumbbell Shoulder Press", "shoulders", "triceps", "dumbbell", "compound"),
        ExDef("Cable Flyes", "chest", "", "cable", "isolation"),
        ExDef("Lateral Raises", "shoulders", "", "dumbbell", "isolation"),
        ExDef("Tricep Pushdowns", "triceps", "", "cable", "isolation"),
        ExDef("Overhead Tricep Extension", "triceps", "", "cable", "isolation"),
        ExDef("Push-Ups", "chest", "triceps,shoulders", "bodyweight", "bodyweight"),
    ],
    # ── Pull ──────────────────────────────────────────────────────
    "pull": [
        ExDef("Barbell Bent-Over Row", "middle_back", "lats,biceps", "barbell", "compound"),
        ExDef("Pull-Ups", "lats", "biceps,middle_back", "bodyweight", "bodyweight"),
        ExDef("Lat Pulldown", "lats", "biceps", "cable", "compound"),
        ExDef("Seated Cable Row", "middle_back", "lats,biceps", "cable", "compound"),
        ExDef("Face Pulls", "shoulders", "traps,middle_back", "cable", "isolation"),
        ExDef("Barbell Curl", "biceps", "forearms", "barbell", "isolation"),
        ExDef("Dumbbell Hammer Curl", "biceps", "forearms", "dumbbell", "isolation"),
        ExDef("Dumbbell Shrugs", "traps", "", "dumbbell", "isolation"),
    ],
    # ── Legs ──────────────────────────────────────────────────────
    "legs": [
        ExDef("Barbell Squat", "quadriceps", "glutes,hamstrings", "barbell", "compound"),
        ExDef("Romanian Deadlift", "hamstrings", "glutes,lower_back", "barbell", "compound"),
        ExDef("Leg Press", "quadriceps", "glutes", "machine", "compound"),
        ExDef("Walking Lunges", "quadriceps", "glutes,hamstrings", "dumbbell", "compound"),
        ExDef("Leg Extension", "quadriceps", "", "machine", "isolation"),
        ExDef("Lying Leg Curl", "hamstrings", "", "machine", "isolation"),
        ExDef("Standing Calf Raises", "calves", "", "machine", "isolation"),
        ExDef("Hip Thrusts", "glutes", "hamstrings", "barbell", "compound"),
    ],
    # ── Upper ─────────────────────────────────────────────────────
    "upper": [
        ExDef("Barbell Bench Press", "chest", "triceps,shoulders", "barbell", "compound"),
        ExDef("Barbell Bent-Over Row", "middle_back", "lats,biceps", "barbell", "compound"),
        ExDef("Dumbbell Shoulder Press", "shoulders", "triceps", "dumbbell", "compound"),
        ExDef("Lat Pulldown", "lats", "biceps", "cable", "compound"),
        ExDef("Cable Flyes", "chest", "", "cable", "isolation"),
        ExDef("Barbell Curl", "biceps", "forearms", "barbell", "isolation"),
        ExDef("Tricep Pushdowns", "triceps", "", "cable", "isolation"),
    ],
    # ── Lower ─────────────────────────────────────────────────────
    "lower": [
        ExDef("Barbell Squat", "quadriceps", "glutes,hamstrings", "barbell", "compound"),
        ExDef("Romanian Deadlift", "hamstrings", "glutes,lower_back", "barbell", "compound"),
        ExDef("Leg Press", "quadriceps", "glutes", "machine", "compound"),
        ExDef("Walking Lunges", "quadriceps", "glutes,hamstrings", "dumbbell", "compound"),
        ExDef("Lying Leg Curl", "hamstrings", "", "machine", "isolation"),
        ExDef("Standing Calf Raises", "calves", "", "machine", "isolation"),
    ],
    # ── Full body ─────────────────────────────────────────────────
    "full_body": [
        ExDef("Barbell Squat", "quadriceps", "glutes,hamstrings", "barbell", "compound"),
        ExDef("Barbell Bench Press", "chest", "triceps,shoulders", "barbell", "compound"),
        ExDef("Barbell Bent-Over Row", "middle_back", "lats,biceps", "barbell", "compound"),
        ExDef("Dumbbell Shoulder Press", "shoulders", "triceps", "dumbbell", "compound"),
        ExDef("Barbell Curl", "biceps", "forearms", "barbell", "isolation"),
        ExDef("Plank", "abdominals", "", "bodyweight", "bodyweight"),
    ],
    # ── Arms ──────────────────────────────────────────────────────
    "arms": [
        ExDef("Barbell Curl", "biceps", "forearms", "barbell", "isolation"),
        ExDef("Dumbbell Hammer Curl", "biceps", "forearms", "dumbbell", "isolation"),
        ExDef("Preacher Curl", "biceps", "", "e_z_curl_bar", "isolation"),
        ExDef("Tricep Pushdowns", "triceps", "", "cable", "isolation"),
        ExDef("Overhead Tricep Extension", "triceps", "", "cable", "isolation"),
        ExDef("Close-Grip Bench Press", "triceps", "chest,shoulders", "barbell", "compound"),
    ],
}

# ── Workout templates per split ──────────────────────────────────────
SESSION_NAMES: dict[str, str] = {
    "push": "Push Day",
    "pull": "Pull Day",
    "legs": "Leg Day",
    "upper": "Upper Body",
    "lower": "Lower Body",
    "full_body": "Full Body",
    "arms": "Arms Day",
}

# ── User profiles ────────────────────────────────────────────────────


class UserProfile(NamedTuple):
    username: str
    display_name: str
    level: str  # beginner | intermediate | expert
    days_per_week: int
    splits: list[str]  # cycle through these split keys
    # Weight multipliers relative to a baseline (makes data realistic
    # per experience level).
    weight_mult: float


USER_PROFILES: list[UserProfile] = [
    UserProfile(
        "alice", "Alice Johnson", "intermediate", 4,
        ["push", "pull", "legs", "upper"], 1.0,
    ),
    UserProfile(
        "bob", "Bob Smith", "beginner", 3,
        ["full_body", "full_body", "full_body"], 0.6,
    ),
    UserProfile(
        "charlie", "Charlie Davis", "expert", 5,
        ["push", "pull", "legs", "push", "pull"], 1.4,
    ),
]

# ── Baseline working weights (kg) per exercise kind ──────────────────
# These are multiplied by UserProfile.weight_mult and jittered.
_BASELINE_WEIGHTS: dict[str, float] = {
    # Compounds
    "Barbell Bench Press": 70,
    "Incline Dumbbell Press": 26,  # per hand
    "Dumbbell Shoulder Press": 22,
    "Barbell Bent-Over Row": 65,
    "Lat Pulldown": 55,
    "Seated Cable Row": 55,
    "Barbell Squat": 90,
    "Romanian Deadlift": 80,
    "Leg Press": 140,
    "Walking Lunges": 16,  # per hand
    "Hip Thrusts": 80,
    "Close-Grip Bench Press": 55,
    # Isolation
    "Cable Flyes": 15,
    "Lateral Raises": 10,
    "Tricep Pushdowns": 25,
    "Overhead Tricep Extension": 20,
    "Face Pulls": 18,
    "Barbell Curl": 30,
    "Dumbbell Hammer Curl": 14,
    "Dumbbell Shrugs": 30,
    "Leg Extension": 45,
    "Lying Leg Curl": 35,
    "Standing Calf Raises": 60,
    "Preacher Curl": 25,
}

# Bodyweight exercises get weight_kg = None
_BODYWEIGHT_EXERCISES = {"Push-Ups", "Pull-Ups", "Plank"}

# ── Session notes pool ───────────────────────────────────────────────
_SESSION_NOTES: list[str | None] = [
    None,
    None,
    None,
    "Felt strong today",
    "Low energy, cut volume slightly",
    "Shoulder felt tight during presses",
    "Great pump",
    "Rushed session, shorter rest periods",
    "Back from 3-day rest, felt fresh",
    "Focused on mind-muscle connection",
    None,
    None,
]


# ── Helpers ──────────────────────────────────────────────────────────


def _working_weight(exercise_name: str, weight_mult: float) -> float | None:
    """Return a jittered working weight for the exercise, or None for BW."""
    if exercise_name in _BODYWEIGHT_EXERCISES:
        return None
    base = _BASELINE_WEIGHTS.get(exercise_name)
    if base is None:
        return None
    scaled = base * weight_mult
    # +/- 10 % jitter, rounded to nearest 2.5
    jittered = scaled * random.uniform(0.90, 1.10)
    return round(jittered / 2.5) * 2.5


def _warmup_weight(working: float) -> float:
    """~50 % of working weight, rounded to 2.5."""
    return round((working * 0.5) / 2.5) * 2.5


def _generate_sets(
    ex: ExDef, weight_mult: float
) -> list[dict]:
    """Return a list of set dicts for one exercise."""
    sets: list[dict] = []
    working = _working_weight(ex.name, weight_mult)

    if ex.kind == "compound":
        # 1 warmup set + 3-5 working sets
        n_working = random.choice([3, 4, 4, 5])
        if working is not None:
            sets.append(dict(
                set_number=1, reps=random.choice([8, 10, 12]),
                weight_kg=_warmup_weight(working),
                rpe=None, is_warmup=1, notes=None,
            ))
        for i in range(n_working):
            reps = random.choice([5, 6, 8, 8, 10])
            rpe = round(random.uniform(7.0, 9.5), 1) if random.random() < 0.4 else None
            sets.append(dict(
                set_number=len(sets) + 1, reps=reps,
                weight_kg=working, rpe=rpe, is_warmup=0, notes=None,
            ))
    elif ex.kind == "isolation":
        # 3-4 working sets, higher rep
        n_sets = random.choice([3, 3, 4])
        for i in range(n_sets):
            reps = random.choice([10, 12, 12, 15])
            rpe = round(random.uniform(7.5, 9.0), 1) if random.random() < 0.3 else None
            sets.append(dict(
                set_number=i + 1, reps=reps,
                weight_kg=working, rpe=rpe, is_warmup=0, notes=None,
            ))
    else:
        # bodyweight: 3-4 sets
        n_sets = random.choice([3, 3, 4])
        for i in range(n_sets):
            if ex.name == "Plank":
                reps = random.choice([1, 1, 1])  # "1 rep" = one timed hold
            else:
                reps = random.choice([6, 8, 10, 12, 15])
            sets.append(dict(
                set_number=i + 1, reps=reps,
                weight_kg=None, rpe=None, is_warmup=0, notes=None,
            ))

    return sets


def _pick_exercises(split: str, level: str) -> list[ExDef]:
    """Pick a subset of exercises for one session."""
    pool = EXERCISES[split]
    if level == "beginner":
        n = random.choice([3, 4])
    elif level == "intermediate":
        n = random.choice([5, 6])
    else:
        n = random.choice([6, 7])
    n = min(n, len(pool))
    # Always include the first exercise (the main compound), then sample
    chosen = [pool[0]] + random.sample(pool[1:], n - 1)
    return chosen


# ── Main seeder ──────────────────────────────────────────────────────


def seed(reset: bool = False) -> None:
    if reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)

    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    # Check if data already exists
    if session.query(User).count() > 0 and not reset:
        print("Data already exists. Use --reset to re-seed.")
        session.close()
        return

    # ── Reference date: 6 weeks back from "today" ────────────────
    today = date(2026, 7, 29)
    start_date = today - timedelta(weeks=6)

    total_sessions = 0
    total_exercises = 0
    total_sets = 0

    for profile in USER_PROFILES:
        user = User(
            username=profile.username,
            display_name=profile.display_name,
            created_at=datetime(2026, 1, 1),
        )
        session.add(user)
        session.flush()  # get user.id

        # Generate sessions across 6 weeks
        current = start_date
        split_idx = 0
        rest_days = 0

        while current <= today:
            # Rest day logic: train `days_per_week` out of 7
            day_of_week = current.weekday()  # 0=Mon
            # Simple schedule: skip weekends for beginners, distribute
            # training days reasonably.
            if profile.days_per_week <= 3:
                # Train Mon/Wed/Fri
                train_days = {0, 2, 4}
            elif profile.days_per_week == 4:
                # Mon/Tue/Thu/Fri
                train_days = {0, 1, 3, 4}
            else:
                # Mon-Fri
                train_days = {0, 1, 2, 3, 4}

            if day_of_week not in train_days:
                current += timedelta(days=1)
                continue

            # Occasionally skip a session (life happens) ~10 %
            if random.random() < 0.10:
                current += timedelta(days=1)
                continue

            split_key = profile.splits[split_idx % len(profile.splits)]
            split_idx += 1

            duration = random.randint(40, 90)
            ws = WorkoutSession(
                user_id=user.id,
                session_date=current,
                session_name=SESSION_NAMES[split_key],
                notes=random.choice(_SESSION_NOTES),
                duration_minutes=duration,
                created_at=datetime.combine(current, datetime.min.time()),
            )
            session.add(ws)
            session.flush()
            total_sessions += 1

            exercises = _pick_exercises(split_key, profile.level)
            for order, ex in enumerate(exercises, start=1):
                se = SessionExercise(
                    session_id=ws.id,
                    exercise_name=ex.name,
                    exercise_order=order,
                    primary_muscle=ex.primary,
                    secondary_muscles=ex.secondary or None,
                    equipment=ex.equipment,
                    notes=None,
                )
                session.add(se)
                session.flush()
                total_exercises += 1

                sets_data = _generate_sets(ex, profile.weight_mult)
                for sd in sets_data:
                    es = ExerciseSet(exercise_id=se.id, **sd)
                    session.add(es)
                    total_sets += 1

            current += timedelta(days=1)

    session.commit()
    session.close()

    print(f"\nSeed complete!")
    print(f"  Users:     {len(USER_PROFILES)}")
    print(f"  Sessions:  {total_sessions}")
    print(f"  Exercises: {total_exercises}")
    print(f"  Sets:      {total_sets}")


# ── CLI entry point ──────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the workout-log database")
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop all tables before re-creating and seeding",
    )
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
