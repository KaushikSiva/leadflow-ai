# LeadFlow AI

LeadFlow AI is an internal prospecting workspace built with FastAPI, SQLAlchemy, Jinja, and a background worker. It discovers LinkedIn-first leads via Apify, scores them with OpenAI, enriches kept leads with phone data, and hands manual calls to the sibling `voicecall` project.

## Services
- `web`: HTML workspace plus JSON API.
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
python3 -m pip install -e '.[dev]'
cp .env.example .env
docker compose up --build
```

The web app listens on `http://localhost:8080`.

## Test
```bash
python3 -m pytest -q
```

# leadflow-ai
