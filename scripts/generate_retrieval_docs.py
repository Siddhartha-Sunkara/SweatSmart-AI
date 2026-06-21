import os
import json
from pathlib import Path
from tqdm import tqdm

# =====================================================
# CONFIG
# =====================================================


INPUT_FOLDER = "Enriched Exercises"
OUTPUT_FOLDER = "data/exercises"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# =====================================================
# NORMALIZATION HELPERS
# =====================================================

EQUIPMENT_MAPPING = {
    "body only": "bodyweight",
    "body_only": "bodyweight",
    "medicine ball": "medicine_ball",
    "exercise ball": "exercise_ball",
    "e-z curl bar": "ez_curl_bar"
}


def normalize_text(text):

    if not text:
        return ""

    text = str(text).strip().lower()

    text = text.replace("-", "_")
    text = text.replace(" ", "_")

    return text


def ensure_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def normalize_equipment(equipment):

    equipment_list = ensure_list(equipment)

    normalized = []

    for item in equipment_list:

        item = normalize_text(item)

        item = EQUIPMENT_MAPPING.get(item, item)

        normalized.append(item)

    return list(set(normalized))


def clean_string_list(values):

    cleaned = []

    for value in ensure_list(values):

        if isinstance(value, dict):
            continue

        cleaned.append(normalize_text(value))

    return list(set(cleaned))


def flatten_goal_objects(goals):

    flattened = []

    for goal in ensure_list(goals):

        if isinstance(goal, dict):

            if "goal" in goal:
                flattened.append(
                    normalize_text(goal["goal"])
                )

        else:
            flattened.append(
                normalize_text(goal)
            )

    return list(set(flattened))


def extract_movement_patterns(movement_pattern):

    if not movement_pattern:
        return []

    text = movement_pattern.lower()

    separators = [
        ",",
        "/",
        " and "
    ]

    for sep in separators:
        text = text.replace(sep, "|")

    parts = []

    for part in text.split("|"):

        cleaned = normalize_text(part)

        if cleaned:
            parts.append(cleaned)

    return list(set(parts))


def infer_systemic_fatigue(score):

    if score <= 3:
        return "low"

    if score <= 6:
        return "moderate"

    return "high"


# =====================================================
# DOCUMENT HELPERS
# =====================================================

def format_list(items):

    if not items:
        return "None"

    formatted = []

    for item in ensure_list(items):

        if isinstance(item, dict):

            text = ", ".join(
                f"{k}: {v}"
                for k, v in item.items()
            )

            formatted.append(text)

        else:
            formatted.append(str(item))

    return "\n- " + "\n- ".join(formatted)


# =====================================================
# RETRIEVAL DOCUMENT
# =====================================================

def create_retrieval_document(exercise):

    document = f"""
Exercise: {exercise.get("name", "")}

Category:
{exercise.get("category", "")}

Exercise Type:
{exercise.get("mechanic", "")}

Force Type:
{exercise.get("force", "")}

Difficulty Level:
{exercise.get("level", "")}

Movement Patterns:
{format_list(
    extract_movement_patterns(
        exercise.get("movement_pattern")
    )
)}

Primary Muscles:
{format_list(exercise.get("primaryMuscles", []))}

Secondary Muscles:
{format_list(exercise.get("secondaryMuscles", []))}

Equipment:
{format_list(
    normalize_equipment(
        exercise.get("equipment")
    )
)}

Fatigue Score:
{exercise.get("fatigue_score", "")}

Systemic Fatigue:
{infer_systemic_fatigue(
    float(exercise.get("fatigue_score", 0))
)}

Stimulus To Fatigue Ratio:
{exercise.get("stimulus_to_fatigue_ratio", "")}

Energy Requirement:
{exercise.get("energy_requirement", "")}

Recovery Time:
{exercise.get("recovery_time_hours", "")} hours

Goals:
{format_list(
    flatten_goal_objects(
        exercise.get("goals")
    )
)}

Contraindications:
{format_list(
    exercise.get("contraindications", [])
)}

Exercise Variations:
{format_list(
    exercise.get("exercise_variations", [])
)}

Substitution Options:
{format_list(
    exercise.get("substitution_options", [])
)}

Instructions:
{format_list(
    exercise.get("instructions", [])
)}
"""

    return document.strip()


# =====================================================
# METADATA
# =====================================================

def create_metadata(exercise):

    fatigue_score = float(
        exercise.get("fatigue_score", 0)
    )

    metadata = {

        "exercise_id":
            normalize_text(exercise.get("id")),

        "exercise_name":
            normalize_text(exercise.get("name")),

        "category":
            normalize_text(exercise.get("category")),

        "exercise_type":
            normalize_text(exercise.get("mechanic")),

        "force":
            normalize_text(exercise.get("force")),

        "difficulty_level":
            normalize_text(exercise.get("level")),

        "movement_patterns":
            extract_movement_patterns(
                exercise.get("movement_pattern")
            ),

        "primary_muscles":
            clean_string_list(
                exercise.get("primaryMuscles")
            ),

        "secondary_muscles":
            clean_string_list(
                exercise.get("secondaryMuscles")
            ),

        "equipment":
            normalize_equipment(
                exercise.get("equipment")
            ),

        "fatigue_score":
            fatigue_score,

        "systemic_fatigue":
            infer_systemic_fatigue(fatigue_score),

        "stimulus_to_fatigue_ratio":
            float(
                exercise.get(
                    "stimulus_to_fatigue_ratio",
                    0
                )
            ),

        "energy_requirement":
            normalize_text(
                exercise.get("energy_requirement")
            ),

        "recovery_time_hours":
            int(
                exercise.get(
                    "recovery_time_hours",
                    0
                )
            ),

        "goals":
            flatten_goal_objects(
                exercise.get("goals")
            ),

        "unilateral":
            False
    }

    return metadata


# =====================================================
# PROCESS FILE
# =====================================================

def process_exercise(file_path):

    with open(file_path, "r", encoding="utf-8") as f:
        exercise = json.load(f)

    retrieval_document = create_retrieval_document(exercise)

    metadata = create_metadata(exercise)

    final_output = {

        "id": normalize_text(
            exercise.get("id")
        ),

        "document": retrieval_document,

        "metadata": metadata
    }

    output_path = (
        Path(OUTPUT_FOLDER) / file_path.name
    )

    with open(output_path, "w", encoding="utf-8") as f:

        json.dump(
            final_output,
            f,
            indent=2,
            ensure_ascii=False
        )


# =====================================================
# MAIN
# =====================================================

def main():

    files = list(
        Path(INPUT_FOLDER).glob("*.json")
    )

    print(f"Found {len(files)} exercise files.")

    for file_path in tqdm(files):

        try:

            process_exercise(file_path)

        except Exception as e:

            print(f"\nError processing: {file_path.name}")
            print(str(e))


if __name__ == "__main__":
    main()