"""LLM prompts for the Intent Router Agent."""

from langchain_core.prompts import ChatPromptTemplate

CLASSIFIER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a fitness assistant intent classifier.

Classify the user's message into EXACTLY ONE of the following intents:

- "workout_generation": the user wants a workout plan, routine, or list of exercises.
  Examples: "give me a push workout", "30 min legs day with dumbbells", "I want an upper body routine".

- "workout_history": the user is asking about their past workouts, logged data, personal records, stats, or history.
  Examples: "what is my heaviest bench press?", "how many workouts did I do last week?", "show my recent sessions", "what was my total volume for chest?", "when did I last do squats?".

- "exercise_question": the user is asking about a specific exercise (form, what it targets, alternatives).
  Examples: "what muscles does a deadlift hit?", "is the goblet squat good for quads?".

- "injury_modification": the user mentions pain, soreness, an injury, or asks how to modify exercises around one.
  Examples: "my knee hurts when squatting", "alternatives to bench press for shoulder pain".

- "progression_plan": the user is asking about progressive overload, periodization, or a multi-week plan.
  Examples: "how should I progress my squat over 8 weeks?", "build me a hypertrophy block".

- "nutrition": food, calories, macros, supplements, hydration.
  Examples: "what should I eat post workout?", "how much protein per day?".

- "greeting": hi/hello/thanks/small talk, anything that is not a fitness question.
  Examples: "hey", "thanks!", "what can you do?".

Return ONLY the intent label.
""",
    ),
    (
        "human",
        "{query}",
    ),
])
