# LeadFlow AI

LeadFlow AI is an internal prospecting workspace built with Flask, SQLAlchemy, Jinja, and a background worker. It discovers LinkedIn-first leads via Apify, scores them with OpenAI, enriches kept leads with phone data, and hands manual calls to the sibling `voicecall` project.

## Processes
- `web`: Flask HTML workspace plus JSON API.
- `worker`: Polls queued prompts and runs planning, discovery, scoring, and enrichment.

## Required Environment
Copy `.env.example` to `.env` and set:

- `DATABASE_URL`: Supabase Postgres connection string.
- `OPENAI_API_KEY`
- `APIFY_API_TOKEN`
- `APIFY_PROFILE_ACTOR_ID`
- `APIFY_PHONE_ENRICH_ACTOR_ID`
- `VOICECALL_API_BASE_URL`
- `VOICECALL_API_TOKEN`

## Local Run
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
cp .env.example .env
```

Start the web app:
```bash
source .venv/bin/activate
python -m leadflow.web
```

Start the worker in a second terminal:
```bash
source .venv/bin/activate
python -m leadflow.worker
```

The web app listens on `http://localhost:8081`.

## Docker
Docker files are still in the repo, but the primary run path is local Python rather than Docker.

## Test
```bash
python3 -m pytest -q
```

# leadflow-ai
