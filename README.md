# SweatSmart — LLM Workout Planner

An LLM-driven workout planner that turns a free-form fitness goal
("give me a 30 min advanced push day with dumbbells") into a structured,
retrieval-grounded workout plan.

The stack is built around a LangGraph multi-stage pipeline, Qdrant for
semantic exercise retrieval, a small Groq LLM for query rewriting, a
larger Groq LLM for planning, and a Redis semantic cache for repeat
queries.

---

## Architecture

```
                 ┌──────────────┐
   POST /api/chat│  Intent      │  ┌─ greeting / stub responses
   ──────────────►  Router      │──┤
                 │  (LLM)       │  └─ workout_generation ─┐
                 └──────────────┘                         │
                                                          ▼
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
```

### Pipeline stages

| Stage             | Type             | What it does |
|-------------------|------------------|--------------|
| `query_rewriter`  | LLM              | Resolves free text → canonical slugs (muscles, equipment, experience, movement pattern, duration). Prompt embeds full muscle/difficulty/movement-pattern definitions. |
| `filter_builder`  | deterministic    | Projects the rewritten query into Qdrant filters (`difficulty_level`, `equipment`, `max_fatigue_score`). |
| `decomposer`      | deterministic    | Fans out into one sub-query per target muscle. |
| `retrieve_node`   | tool (async)     | Per-muscle Qdrant retrieval, executed in parallel via LangGraph's `Send` API. |
| `aggregator`      | deterministic    | Dedupes, groups by muscle, ranks the candidate pool. |
| `planner`         | LLM              | Picks 5–7 exercises that cover every target muscle. Llama 3.3 70B. |

The intent router (`POST /api/chat`) is a thin LLM classifier that
delegates `workout_generation` intents to the planner pipeline above
and returns a canned response for everything else.

---

## Tech stack

- **Python 3.12**, FastAPI, Uvicorn
- **LangGraph** for the agent DAG, **LangChain** for prompt + structured output
- **LangSmith** for tracing (optional, via `LANGCHAIN_*` env vars)
- **Groq** for inference
  - `openai/gpt-oss-20b` — intent classifier & query rewriter
  - `llama-3.3-70b-versatile` — planner
- **Qdrant** for vector search (exercise corpus, BGE embeddings)
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
│   ├── graph.py                # builder
│   ├── nodes.py                # classify / greeting / stub / run_workout
│   ├── prompts.py
│   └── schemas.py
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
├── rag/
│   ├── retrieval_pipeline.py   # async Qdrant retrieval
│   └── hybrid.py               # optional BM25+vector hybrid
│
├── scripts/
│   ├── enrich_exercises.py         # JSON enrichment
│   ├── generate_retrieval_docs.py  # build retrieval docs
│   └── upload_to_qdrant.py         # one-off ingestion job
│
├── data/                       # exercise JSON corpus
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
| GET    | `/api/health`         | Aggregate health (Groq + Qdrant) |
| GET    | `/api/groq_health`    | Groq connectivity probe |
| GET    | `/api/qdrant_health`  | Qdrant connectivity probe |
| GET    | `/api/redis_health`   | Redis / semantic cache probe |
| POST   | `/api/chat`           | Intent router (classifies + dispatches) |
| POST   | `/api/workout`        | Direct workout planner pipeline |

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

---

## Configuration

All knobs live in `.env` (see `.env.example`).

| Variable                              | Default                       | Purpose |
|---------------------------------------|-------------------------------|---------|
| `GROQ_API_KEY`                        | —                             | **required** |
| `GROQ_INTENT_MODEL`                   | `openai/gpt-oss-20b`          | Intent classifier model |
| `GROQ_REWRITER_MODEL`                 | `openai/gpt-oss-20b`          | Query rewriter model |
| `GROQ_PLANNER_MODEL`                  | `llama-3.3-70b-versatile`     | Planner model |
| `WORKOUT_LLM_TEMPERATURE`             | `0.3`                         | Temperature for planner / rewriter |
| `LANGCHAIN_TRACING_V2`                | `false`                       | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY`                   | —                             | LangSmith API key |
| `LANGCHAIN_PROJECT`                   | `fitness-ai-agent`            | LangSmith project name |
| `QDRANT_URL`                          | `http://localhost:6333`       | Compose overrides this to `http://qdrant:6333` |
| `REDIS_URL`                           | `redis://localhost:6379`      | Compose overrides this to `redis://redis:6379` |
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
deterministically (`beginner → 5`, `intermediate → 7`, `expert → 10`).

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
```

---

## Notes

- The app is stateless — no sessions, logs, or user data are persisted.
  The only stateful pieces are the Redis semantic cache (TTL'd) and the
  HuggingFace model cache (`hf_cache` named volume).
- `.env` is gitignored and dockerignored. Pass secrets only via
  `docker-compose`'s `env_file`.
- The rewriter LLM (default `gpt-oss-20b`) is small and occasionally
  emits an empty rewrite for unusual phrasing. Bump
  `GROQ_REWRITER_MODEL` to a larger model if you see this in production.
