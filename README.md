# SweatSmart — LLM Workout Planner & History Agent

An LLM-driven fitness platform that combines two intelligent agents:

1. **Workout Planner** — turns a free-form fitness goal
   ("give me a 30 min advanced push day with dumbbells") into a structured,
   retrieval-grounded workout plan.
2. **NL-to-SQL History Agent** — answers natural-language questions about
   your past workout sessions ("what was my heaviest bench press?") by
   generating, validating, and executing SQL against a workout log database.

The stack is built around LangGraph multi-stage pipelines, Qdrant for
semantic exercise retrieval, Groq LLMs for query rewriting / planning /
SQL generation, SQLite for workout history, and a Redis semantic cache for
repeat queries.

---

## Architecture

```
                 ┌──────────────┐
   POST /api/chat│  Intent      │  ┌─ greeting / stub responses
   ──────────────►  Router      │──┤
                 │  (LLM)       │  ├─ workout_generation ──► Workout Planner Pipeline
                 └──────────────┘  └─ workout_history ─────► NL-to-SQL Agent

                                          ┌────────────────────────────┐
   POST /api/workout ─────────────────────►  Workout Planner Pipeline  │
                                          │   (LangGraph DAG)          │
                                          └────────────┬───────────────┘
                                                       │
        ┌──────────────────────────────────────────────┼──────────────────────────────────────────────┐
        │                                              │                                              │
        ▼                                              ▼                                              ▼
 query_rewriter  ─►  filter_builder  ─►  decomposer  ─►  retrieve_node (×N parallel)  ─►  aggregator  ─►  planner
   (LLM)             (deterministic)     (deterministic)   (Qdrant, async)                 (rank/group)    (LLM)


   POST /api/history ─────────────────────► NL-to-SQL Agent (LangGraph DAG)
                                                       │
        ┌──────────────────────────────────────────────┼──────────────────────────┐
        │                                              │                          │
        ▼                                              ▼                          ▼
 schema_inspector ─► query_writer ─► query_validator ─► query_executor ─► response_formatter
  (deterministic)      (LLM)          (regex + LLM)     (SQLite)            (LLM)
                         ▲                                  │
                         └──── retry (up to 2) ◄────────────┘
```

### Workout Planner pipeline stages

| Stage             | Type             | What it does |
|-------------------|------------------|--------------|
| `query_rewriter`  | LLM              | Resolves free text → canonical slugs (muscles, equipment, experience, movement pattern, duration). Prompt embeds full muscle/difficulty/movement-pattern definitions. |
| `filter_builder`  | deterministic    | Projects the rewritten query into Qdrant filters (`difficulty_level`, `equipment`, `max_fatigue_score`). |
| `decomposer`      | deterministic    | Fans out into one sub-query per target muscle. |
| `retrieve_node`   | tool (async)     | Per-muscle Qdrant retrieval, executed in parallel via LangGraph's `Send` API. |
| `aggregator`      | deterministic    | Dedupes, groups by muscle, ranks the candidate pool. |
| `planner`         | LLM              | Picks 5-7 exercises that cover every target muscle. Llama 3.3 70B. |

### NL-to-SQL Agent pipeline stages

| Stage                | Type             | What it does |
|----------------------|------------------|--------------|
| `schema_inspector`   | deterministic    | Extracts DDL schema from SQLAlchemy ORM metadata (cached after first call). |
| `query_writer`       | LLM              | Converts the natural-language question into a SELECT query. Llama 3.3 70B at temperature 0 for deterministic output. Auto-wraps string columns in `LOWER()` for case-insensitive matching. |
| `query_validator`    | regex + LLM      | **Layer 1:** regex blocklist rejects INSERT/UPDATE/DELETE/DROP and multi-statement queries. **Layer 2:** LLM validates safety, correctness, and that the query is scoped to the requesting `user_id`. |
| `query_executor`     | SQLite           | Injects `LIMIT 50` if missing, executes inside a rolled-back transaction (read-only guarantee), with a 5-second timeout. |
| `response_formatter` | LLM              | Converts raw SQL result rows (or errors) into a friendly natural-language answer. |

On execution failure the agent retries up to 2 times, feeding the error
message back into the query writer so the LLM can self-correct.

### Intent Router

The intent router (`POST /api/chat`) is a thin LLM classifier that
recognises seven intents:

| Intent                | Routed to |
|-----------------------|-----------|
| `workout_generation`  | Workout Planner Pipeline |
| `workout_history`     | NL-to-SQL Agent |
| `greeting`            | Canned greeting response |
| `exercise_question`   | Stub (coming soon) |
| `injury_modification` | Stub (coming soon) |
| `progression_plan`    | Stub (coming soon) |
| `nutrition`           | Stub (coming soon) |

---

## Tech stack

- **Python 3.12**, FastAPI, Uvicorn
- **LangGraph** for the agent DAGs, **LangChain** for prompt + structured output
- **LangSmith** for tracing (optional, via `LANGCHAIN_*` env vars)
- **Groq** for inference
  - `openai/gpt-oss-20b` — intent classifier, query rewriter, SQL validator, SQL response formatter
  - `llama-3.3-70b-versatile` — workout planner, SQL query writer
- **Qdrant** for vector search (exercise corpus, BGE embeddings)
- **SQLite** for workout history log (via SQLAlchemy ORM)
- **Redis Stack** for the semantic chat cache (RediSearch vector index)
- **sentence-transformers** with `BAAI/bge-small-en-v1.5`

---

## Repo layout

```
.
├── api/                        # FastAPI app
│   ├── main.py                 # lifespan + middleware + router mounting
│   ├── config.py               # pydantic-settings config
│   ├── exceptions.py           # custom exception types + handlers
│   ├── middleware.py           # request-id + timeout
│   ├── models/                 # request / response schemas
│   ├── routers/                # health.py, agent_router.py
│   └── services/               # chat / workout / health / semantic_cache
│
├── intent_agent/               # Intent router (LangGraph)
│   ├── agent.py                # aask / ask entry points
│   ├── graph.py                # builder + conditional routing
│   ├── nodes.py                # classify / greeting / stub / run_workout / run_nl_to_sql
│   ├── prompts.py              # classifier system prompt
│   ├── schemas.py              # IntentClassification
│   └── state.py                # RouterState
│
├── workout_planner_agent/      # Workout planner (LangGraph)
│   ├── agent.py                # aask / ask
│   ├── graph.py                # DAG wiring
│   ├── rules.py                # canonical vocabularies + definitions
│   ├── prompts.py              # rewriter & planner prompts
│   ├── schemas.py              # RewrittenQuery, CommonFilters, ExerciseDoc, WorkoutPlan, ...
│   ├── state.py                # WorkoutState (TypedDict)
│   └── pipeline/
│       ├── query_rewriter.py
│       ├── filter_builder.py
│       ├── decomposer.py
│       ├── retriever.py
│       ├── aggregator.py
│       └── planner.py
│
├── nl_to_sql_agent/            # NL-to-SQL history agent (LangGraph)
│   ├── agent.py                # aask / ask entry points
│   ├── config.py               # model + timeout config
│   ├── graph.py                # DAG wiring + retry routing
│   ├── schemas.py              # GeneratedSQL, SQLValidation, FormattedResponse
│   ├── state.py                # NLToSQLState (TypedDict)
│   └── pipeline/
│       ├── schema_inspector.py # extract DDL from ORM
│       ├── query_writer.py     # NL → SQL (LLM)
│       ├── query_validator.py  # regex blocklist + LLM safety check
│       ├── query_executor.py   # execute with rollback + timeout
│       └── response_formatter.py # results → natural language
│
├── db/                         # Workout log database
│   ├── engine.py               # SQLAlchemy engine + Base
│   ├── models.py               # User, WorkoutSession, SessionExercise, ExerciseSet
│   ├── seed.py                 # seed script for demo data
│   └── __main__.py             # create tables + seed
│
├── rag/
│   ├── retrieval_pipeline.py   # async Qdrant retrieval
│   └── hybrid.py               # optional BM25+vector hybrid
│
├── scripts/
│   ├── enrich_exercises.py         # JSON enrichment
│   ├── generate_retrieval_docs.py  # build retrieval docs
│   └── upload_to_qdrant.py         # one-off ingestion job
│
├── data/                       # exercise JSON corpus + workout_log.db
├── docker-compose.yml          # qdrant + redis + app + (profile) ingest
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Running it

### Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- A Groq API key — https://console.groq.com/keys

### 1. Configure environment

```bash
cp .env.example .env
# then fill in GROQ_API_KEY and (optionally) LANGCHAIN_API_KEY
```

### 2. Bring the stack up

```bash
docker compose up -d --build
```

Three services start:

| Service          | Container             | Ports             |
|------------------|-----------------------|-------------------|
| FastAPI app      | `sweatsmart-app`      | `8000`            |
| Qdrant           | `sweatsmart-qdrant`   | `6333`, `6334`    |
| Redis Stack      | `sweatsmart-redis`    | `6379`, `8001` (RedisInsight UI) |

The compose file mounts the Qdrant storage path from
`${QDRANT_STORAGE_PATH:-C:/Users/Asus/qdrant_storage}` — point this at
your own host folder if you're not on the original dev machine.

### 3. (One-off) Ingest the exercise corpus into Qdrant

```bash
docker compose --profile ingest run --rm ingest
```

This runs `python -m scripts.upload_to_qdrant` inside the app image.

### 4. Useful compose commands

```bash
docker compose ps              # status
docker compose logs -f app     # follow app logs
docker compose down            # stop the stack
docker compose down -v         # stop + drop named volumes (Redis cache, HF model cache)
```

---

## API

After startup the app listens on http://localhost:8000.

| Method | Path                  | Purpose |
|-------:|-----------------------|---------|
| GET    | `/`                   | Welcome message |
| GET    | `/api/health`         | Aggregate health (Groq + Qdrant) |
| GET    | `/api/groq_health`    | Groq connectivity probe |
| GET    | `/api/qdrant_health`  | Qdrant connectivity probe |
| GET    | `/api/redis_health`   | Redis / semantic cache probe |
| POST   | `/api/chat`           | Intent router (classifies + dispatches to workout planner or history agent) |
| POST   | `/api/workout`        | Direct workout planner pipeline |
| POST   | `/api/history`        | Direct NL-to-SQL history agent |

### `POST /api/chat`

```json
{
  "user_prompt": "give me a beginner push workout with dumbbells"
}
```

Response:

```json
{
  "query": "give me a beginner push workout with dumbbells",
  "intent": "workout_generation",
  "result": { "workout_plan": { "...": "..." } },
  "response": "Workout Plan: Beginner Push Day ...",
  "cached": false,
  "cache_distance": null
}
```

Repeat queries within the configured semantic distance hit the Redis
cache and short-circuit the pipeline.

### `POST /api/workout`

Skips the intent router and runs the planner pipeline directly.

```json
{
  "user_prompt": "30 min advanced full body workout with bodyweight",
  "filters": { "equipment": ["bodyweight"] }
}
```

Response:

```json
{
  "workout_plan": {
    "plan_title": "Advanced Full Body Workout",
    "target_muscle": "full body: chest, lats, quadriceps, hamstrings, shoulders, abdominals",
    "difficulty": "expert",
    "estimated_duration_minutes": 60,
    "exercises": [
      {
        "exercise_name": "handstand_push_ups",
        "sets": 3,
        "reps": "8-12",
        "rest_seconds": 60,
        "coaching_cue": "Keep your core tight throughout the movement."
      }
    ],
    "general_tip": "..."
  }
}
```

`filters` is optional and overrides anything the LLM rewriter inferred.
Recognised keys: `difficulty_level`, `equipment`, `max_fatigue_score`.

### `POST /api/history`

Queries the workout log database using natural language. Requires a
`user_id` to scope results.

```json
{
  "user_prompt": "Show me my last 5 workout sessions",
  "user_id": 1
}
```

Response:

```json
{
  "query": "Show me my last 5 workout sessions",
  "user_id": 1,
  "generated_sql": "SELECT ws.session_date, ws.session_name, ws.notes, ws.duration_minutes FROM users u JOIN workout_sessions ws ON u.id = ws.user_id WHERE u.id = 1 ORDER BY ws.session_date DESC LIMIT 5",
  "is_valid": true,
  "row_count": 5,
  "response": "Here are your most recent five workout sessions: ..."
}
```

---

## Examples

### Workout Planner examples

All examples use `POST /api/chat` with `{"user_prompt": "..."}`.

#### 1. Beginner chest workout with dumbbells

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "Give me a 30 minute beginner chest workout with dumbbells"}'
```

Response (workout plan):

```json
{
  "plan_title": "30 Minute Beginner Chest Workout with Dumbbells",
  "target_muscle": "chest",
  "difficulty": "beginner",
  "estimated_duration_minutes": 30,
  "exercises": [
    {
      "exercise_name": "one_arm_dumbbell_bench_press",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Squeeze your chest muscles at the top of the movement"
    },
    {
      "exercise_name": "dumbbell_flyes",
      "sets": 3, "reps": "10-15", "rest_seconds": 60,
      "coaching_cue": "Keep your arms straight and focus on squeezing your chest muscles"
    },
    {
      "exercise_name": "incline_dumbbell_flyes",
      "sets": 3, "reps": "10-12", "rest_seconds": 60,
      "coaching_cue": "Target the upper chest muscles by keeping your arms at an angle"
    },
    {
      "exercise_name": "one_arm_flat_bench_dumbbell_flye",
      "sets": 3, "reps": "10-12", "rest_seconds": 60,
      "coaching_cue": "Focus on slow and controlled movements to engage your chest muscles"
    }
  ],
  "general_tip": "Start with lighter weights and focus on proper form and technique throughout the workout"
}
```

#### 2. Beginner leg day with machines

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "beginner leg day with machines"}'
```

Response (workout plan):

```json
{
  "plan_title": "Beginner Leg Day with Machines",
  "target_muscle": "legs: quadriceps, hamstrings, glutes, calves",
  "difficulty": "beginner",
  "estimated_duration_minutes": 45,
  "exercises": [
    {
      "exercise_name": "leg_press",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Keep your back against the pad and push through your heels"
    },
    {
      "exercise_name": "seated_leg_curl",
      "sets": 3, "reps": "10-15", "rest_seconds": 60,
      "coaching_cue": "Focus on squeezing your hamstrings at the top of the movement"
    },
    {
      "exercise_name": "calf_press_on_the_leg_press_machine",
      "sets": 3, "reps": "12-15", "rest_seconds": 60,
      "coaching_cue": "Raise the platform all the way up and then lower it back down slowly"
    },
    {
      "exercise_name": "smith_machine_stiff_legged_deadlift",
      "sets": 3, "reps": "8-10", "rest_seconds": 90,
      "coaching_cue": "Keep your back straight and lift with your legs, not your back"
    },
    {
      "exercise_name": "single_leg_leg_extension",
      "sets": 3, "reps": "10-12", "rest_seconds": 60,
      "coaching_cue": "Lift the weight up with one leg and then switch to the other"
    }
  ],
  "general_tip": "Start with lighter weights and focus on proper form and technique. As you get stronger, you can gradually increase the weight and intensity of your workout."
}
```

#### 3. Intermediate back and biceps pull workout with cables and barbells

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "Build me an intermediate back and biceps pull workout with cables and barbells"}'
```

Response (workout plan):

```json
{
  "plan_title": "Intermediate Back and Biceps Pull Workout",
  "target_muscle": "pull: lats, middle back, biceps",
  "difficulty": "intermediate",
  "estimated_duration_minutes": 45,
  "exercises": [
    {
      "exercise_name": "elevated_cable_rows",
      "sets": 3, "reps": "8-12", "rest_seconds": 90,
      "coaching_cue": "Keep your core engaged and focus on squeezing your lats"
    },
    {
      "exercise_name": "seated_one_arm_cable_pulley_rows",
      "sets": 3, "reps": "10-15", "rest_seconds": 90,
      "coaching_cue": "Maintain a straight back and pull the cable towards your side"
    },
    {
      "exercise_name": "reverse_grip_bent_over_rows",
      "sets": 3, "reps": "8-12", "rest_seconds": 120,
      "coaching_cue": "Keep your back straight and lift the barbell with your middle back"
    },
    {
      "exercise_name": "overhead_cable_curl",
      "sets": 3, "reps": "10-12", "rest_seconds": 90,
      "coaching_cue": "Focus on curling the cable with your biceps"
    },
    {
      "exercise_name": "lying_high_bench_barbell_curl",
      "sets": 3, "reps": "8-10", "rest_seconds": 120,
      "coaching_cue": "Keep your upper arms still and curl the barbell with your biceps"
    }
  ],
  "general_tip": "Start with a warm-up routine and adjust the weights according to your fitness level"
}
```

#### 4. Shoulder and triceps bodyweight push session

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "Give me a quick 20 minute shoulder and triceps push session with bodyweight exercises"}'
```

Response (workout plan):

```json
{
  "plan_title": "Quick 20 Minute Shoulder and Triceps Push Session",
  "target_muscle": "push: chest, shoulders, triceps",
  "difficulty": "intermediate",
  "estimated_duration_minutes": 20,
  "exercises": [
    {
      "exercise_name": "pushups",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Keep your core engaged and lower your body until your chest almost touches the ground"
    },
    {
      "exercise_name": "dips___triceps_version",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Lower your body until your arms are bent at a 90 degree angle"
    },
    {
      "exercise_name": "handstand_push_ups",
      "sets": 3, "reps": "8-12", "rest_seconds": 90,
      "coaching_cue": "Keep your body in a straight line and lower your body until your head almost touches the ground"
    },
    {
      "exercise_name": "pushups_(close_and_wide_hand_positions)",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Keep your core engaged and lower your body until your chest almost touches the ground"
    },
    {
      "exercise_name": "standing_towel_triceps_extension",
      "sets": 3, "reps": "12-15", "rest_seconds": 60,
      "coaching_cue": "Keep your arms straight and lift the towel until your arms are fully extended"
    }
  ],
  "general_tip": "Start with a dynamic warm-up and rest for 60-90 seconds between sets"
}
```

#### 5. Expert full body workout with dumbbells and barbells

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "Create an expert full body workout using dumbbells and barbells for 45 minutes"}'
```

Response (workout plan):

```json
{
  "plan_title": "Expert Full Body Workout",
  "target_muscle": "full body: chest, lats, quadriceps, hamstrings, shoulders, abdominals",
  "difficulty": "expert",
  "estimated_duration_minutes": 45,
  "exercises": [
    {
      "exercise_name": "speed_squats",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Keep your back straight and descend slowly"
    },
    {
      "exercise_name": "power_snatch",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Explode upward from the hips"
    },
    {
      "exercise_name": "push_press",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Extend your hips and push upward"
    },
    {
      "exercise_name": "press_sit_up",
      "sets": 3, "reps": "12-15", "rest_seconds": 60,
      "coaching_cue": "Lift the barbell straight up"
    },
    {
      "exercise_name": "clean_and_jerk",
      "sets": 3, "reps": "8-12", "rest_seconds": 60,
      "coaching_cue": "Receive the barbell in a partial squat"
    }
  ],
  "general_tip": "Focus on proper form and explosive power throughout the workout"
}
```

### NL-to-SQL History Agent examples

All examples use `POST /api/history` with `{"user_prompt": "...", "user_id": 1}`.

#### 1. Query recent workout sessions

```bash
curl -X POST http://localhost:8000/api/history \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "Show me my last 5 workout sessions", "user_id": 1}'
```

Generated SQL:

```sql
SELECT ws.session_date, ws.session_name, ws.notes, ws.duration_minutes
FROM users u
JOIN workout_sessions ws ON u.id = ws.user_id
WHERE u.id = 1
ORDER BY ws.session_date DESC
LIMIT 5
```

Response:

> Here are the details of your most recent five workout sessions:
>
> - **July 28, 2026 - Pull Day** - Duration: 48 min - Notes: Focused on mind-muscle connection
> - **July 27, 2026 - Push Day** - Duration: 45 min - Notes: Focused on mind-muscle connection
> - **July 24, 2026 - Upper Body** - Duration: 51 min
> - **July 23, 2026 - Leg Day** - Duration: 88 min - Notes: Low energy, cut volume slightly
> - **July 21, 2026 - Pull Day** - Duration: 43 min - Notes: Rushed session, shorter rest periods

#### 2. Find exercises for a specific muscle group

```bash
curl -X POST http://localhost:8000/api/history \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "Which exercises did I do for chest in my last workout?", "user_id": 1}'
```

Generated SQL:

```sql
SELECT se.exercise_name
FROM workout_sessions ws
JOIN session_exercises se ON ws.id = se.session_id
JOIN exercise_sets es ON se.id = es.exercise_id
WHERE ws.user_id = 1
  AND LOWER(se.primary_muscle) = LOWER('chest')
ORDER BY ws.session_date DESC
LIMIT 1
```

Response:

> In your last workout, you performed the **Barbell Bench Press** for chest.

#### 3. Calculate training volume

```bash
curl -X POST http://localhost:8000/api/history \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "What is my total training volume for squats?", "user_id": 1}'
```

Generated SQL:

```sql
SELECT SUM(es.weight_kg * es.reps) AS total_training_volume
FROM users u
JOIN workout_sessions ws ON u.id = ws.user_id
JOIN session_exercises se ON ws.id = se.session_id
JOIN exercise_sets es ON se.id = es.exercise_id
WHERE u.id = 1
  AND LOWER(se.exercise_name) = LOWER('Squats')
```

#### 4. Count workouts in a time period

```bash
curl -X POST http://localhost:8000/api/history \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "How many workouts did I do this month?", "user_id": 1}'
```

Generated SQL:

```sql
SELECT COUNT(*) AS total_workouts
FROM users
JOIN workout_sessions ON users.id = workout_sessions.user_id
WHERE users.id = 1
  AND strftime('%Y-%m', workout_sessions.session_date) = strftime('%Y-%m', 'now')
LIMIT 50
```

#### 5. Personal records

```bash
curl -X POST http://localhost:8000/api/history \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "What was my heaviest bench press?", "user_id": 1}'
```

Generated SQL:

```sql
SELECT MAX(es.weight_kg) AS heaviest_bench_press
FROM users u
JOIN workout_sessions ws ON u.id = ws.user_id
JOIN session_exercises se ON ws.id = se.session_id
JOIN exercise_sets es ON se.id = es.exercise_id
WHERE u.id = 1
  AND LOWER(se.exercise_name) = LOWER('Bench Press')
```

---

## Workout Log Database Schema

The NL-to-SQL agent queries a SQLite database with the following schema:

```
users
├── id              INTEGER  PK
├── username        VARCHAR(50)   UNIQUE
├── display_name    VARCHAR(100)
└── created_at      DATETIME

workout_sessions
├── id              INTEGER  PK
├── user_id         INTEGER  FK → users.id
├── session_date    DATE
├── session_name    VARCHAR(200)
├── notes           TEXT
├── duration_minutes INTEGER
└── created_at      DATETIME

session_exercises
├── id              INTEGER  PK
├── session_id      INTEGER  FK → workout_sessions.id
├── exercise_name   VARCHAR(200)
├── exercise_order  INTEGER
├── primary_muscle  VARCHAR(50)
├── secondary_muscles VARCHAR(200)
├── equipment       VARCHAR(50)
└── notes           TEXT

exercise_sets
├── id              INTEGER  PK
├── exercise_id     INTEGER  FK → session_exercises.id
├── set_number      INTEGER
├── reps            INTEGER  (CHECK > 0)
├── weight_kg       FLOAT
├── rpe             FLOAT
├── is_warmup       INTEGER  (0 or 1)
└── notes           TEXT
```

### Safety guarantees

The NL-to-SQL agent enforces multiple safety layers:

- **User scoping** — every generated query must filter by `user_id` (enforced by the LLM validator)
- **Read-only enforcement** — triple-layer check: regex blocklist rejects mutating keywords (INSERT, UPDATE, DELETE, DROP, etc.), LLM validates safety, and execution always runs inside a rolled-back transaction
- **Row limit** — `LIMIT 50` is injected if missing
- **Timeout** — 5-second query execution timeout
- **Self-correction** — on execution errors, retries up to 2 times with error context fed back to the LLM

---

## Configuration

All knobs live in `.env` (see `.env.example`).

| Variable                              | Default                       | Purpose |
|---------------------------------------|-------------------------------|---------|
| `GROQ_API_KEY`                        | —                             | **required** |
| `GROQ_INTENT_MODEL`                   | `openai/gpt-oss-20b`          | Intent classifier model |
| `GROQ_REWRITER_MODEL`                 | `openai/gpt-oss-20b`          | Query rewriter model |
| `GROQ_PLANNER_MODEL`                  | `llama-3.3-70b-versatile`     | Planner model |
| `GROQ_SQL_WRITER_MODEL`              | `llama-3.3-70b-versatile`     | NL-to-SQL query writer model |
| `GROQ_SQL_VALIDATOR_MODEL`           | `openai/gpt-oss-20b`          | SQL validator model |
| `GROQ_SQL_FORMATTER_MODEL`           | `openai/gpt-oss-20b`          | SQL response formatter model |
| `WORKOUT_LLM_TEMPERATURE`             | `0.3`                         | Temperature for planner / rewriter |
| `LANGCHAIN_TRACING_V2`                | `false`                       | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY`                   | —                             | LangSmith API key |
| `LANGCHAIN_PROJECT`                   | `fitness-ai-agent`            | LangSmith project name |
| `QDRANT_URL`                          | `http://localhost:6333`       | Compose overrides this to `http://qdrant:6333` |
| `REDIS_URL`                           | `redis://localhost:6379`      | Compose overrides this to `redis://redis:6379` |
| `WORKOUT_LOG_DB`                      | `data/workout_log.db`         | Path to the SQLite workout log database |
| `SEMANTIC_CACHE_ENABLED`              | `true`                        | Toggle the chat semantic cache |
| `SEMANTIC_CACHE_INDEX_NAME`           | `chat_semcache`               | RediSearch index name |
| `SEMANTIC_CACHE_DISTANCE_THRESHOLD`   | `0.1`                         | Cosine distance threshold for cache hits |
| `SEMANTIC_CACHE_TTL_SECONDS`          | `3600`                        | Cache entry TTL |
| `SEMANTIC_CACHE_EMBED_MODEL`          | `BAAI/bge-small-en-v1.5`      | Cache embedding model (also used by retrieval) |
| `USE_HYBRID`                          | `false`                       | Switch to BM25 + vector hybrid retrieval |
| `RETRIEVAL_TOP_K`                     | `8`                           | Per-muscle top-k |
| `RETRIEVAL_CANDIDATE_POOL`            | `30`                          | Aggregated candidate pool size cap |

---

## Canonical vocabularies

The rewriter LLM is prompted with definitions of every canonical slug
so it can resolve synonyms semantically rather than via brittle keyword
matching. The vocabularies live in
[`workout_planner_agent/rules.py`](workout_planner_agent/rules.py) and
must mirror the Qdrant payload:

- `MUSCLES` — 17 primary muscle slugs
- `EQUIPMENT` — 12 equipment slugs (matches the corpus)
- `EXPERIENCE_LEVELS` — `beginner | intermediate | expert`
- `MOVEMENT_PATTERNS` — `push | pull | legs | upper | lower | arms | back | core | full_body | custom`

`EXPERIENCE_TO_MAX_FATIGUE` is the only numeric policy still applied
deterministically (`beginner -> 5`, `intermediate -> 7`, `expert -> 10`).

---

## Local development (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Start your own Qdrant + Redis Stack (e.g. via docker run) and point
# QDRANT_URL / REDIS_URL at them in .env.

uvicorn api.main:app --reload --port 8000
```

Quick CLI smoke test of the agents themselves:

```bash
python -m intent_agent.agent
python -m workout_planner_agent.agent
python -m nl_to_sql_agent.agent
```

---

## Notes

- The app is stateless — no sessions, logs, or user data are persisted.
  The only stateful pieces are the Redis semantic cache (TTL'd), the
  SQLite workout log (bundled in the image), and the HuggingFace model
  cache (`hf_cache` named volume).
- `.env` is gitignored and dockerignored. Pass secrets only via
  `docker-compose`'s `env_file`.
- The rewriter LLM (default `gpt-oss-20b`) is small and occasionally
  emits an empty rewrite for unusual phrasing. Bump
  `GROQ_REWRITER_MODEL` to a larger model if you see this in production.
- The NL-to-SQL agent uses temperature 0 for deterministic SQL
  generation. The query writer model (`llama-3.3-70b-versatile`) is
  chosen for its strong SQL reasoning capabilities.
