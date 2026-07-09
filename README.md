# ai-cs-helper
9팀 AI-CS-helper

## Run with Docker

Copy `.env.example` to `.env` and fill the secret values.

```powershell
docker compose up --build
```

Backend health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

LiteLLM listens on `http://localhost:4000` and exposes OpenAI-compatible `/v1` routes. The backend uses `http://litellm:4000/v1` inside Docker Compose.

## Embedding Demo

Store one console input in Supabase:

```powershell
uv run python scripts/embedding_demo.py add
```

Search the 3 most similar rows:

```powershell
uv run python scripts/embedding_demo.py search
```
