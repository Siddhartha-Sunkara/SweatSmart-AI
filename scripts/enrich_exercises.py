import os
import json
from pathlib import Path
from tqdm import tqdm
import ollama

MODEL = "qwen2.5:7b"

INPUT_FOLDER = "Exercise JSONs"
OUTPUT_FOLDER = "Enriched Exercises"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

PROMPT_TEMPLATE = """
You are an elite fitness trainer and exercise scientist.

Given the following exercise JSON,
generate ONLY valid JSON containing these enrichment fields:

{
  "movement_pattern": "",
  "fatigue_score": 1,
  "stimulus_to_fatigue_ratio": 1,
  "energy_requirement": "",
  "recovery_time_hours": 0,
  "optimal_workout_position": "",
  "substitution_options": [],
  "exercise_variations": [],
  "contraindications": [],
  "goals": []
}

RULES:
- Return ONLY valid JSON
- No markdown
- No explanations
- Use realistic fitness knowledge
- fatigue_score should reflect systemic fatigue
- stimulus_to_fatigue_ratio should reflect hypertrophy efficiency

Exercise JSON:
"""

def call_ollama(exercise_data):

    prompt = f"""
{PROMPT_TEMPLATE}

{json.dumps(exercise_data, indent=2)}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0.2
        }
    )

    return response["message"]["content"]

def clean_json_response(raw_response):

    cleaned = raw_response.strip()

    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```", "")

    return cleaned.strip()

def enrich_exercise(exercise_data):

    raw_response = call_ollama(exercise_data)

    cleaned_response = clean_json_response(raw_response)

    try:
        enriched_fields = json.loads(cleaned_response)

    except json.JSONDecodeError:

        print(f"Failed to parse JSON for: {exercise_data.get('name')}")
        print(cleaned_response)

        return None

    merged = {
        **exercise_data,
        **enriched_fields
    }

    return merged

def main():

    files = list(Path(INPUT_FOLDER).glob("*.json"))

    print(f"Found {len(files)} exercise files.")

    for file_path in tqdm(files):

        try:

            with open(file_path, "r", encoding="utf-8") as f:
                exercise_data = json.load(f)

            enriched = enrich_exercise(exercise_data)

            if enriched is None:
                continue

            output_path = Path(OUTPUT_FOLDER) / file_path.name

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(enriched, f, indent=2)

        except Exception as e:

            print(f"Error processing {file_path.name}")
            print(str(e))

if __name__ == "__main__":
    main()