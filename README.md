# XpertForma Platform

Django REST API backend for the XpertForma sports training management platform.

## Tech Stack

- Python 3.12+
- Django 6.0
- Django REST Framework + SimpleJWT
- PostgreSQL (via `dj_database_url`) / SQLite for development
- WhiteNoise for static files

## Setup

```bash
# 1. Clone and create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create a .env file (see below)
copy .env.example .env       # then edit values

# 4. Apply migrations and seed positions
python manage.py migrate

# 5. Run the dev server
python manage.py runserver
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | prod | `dev-secret-key` (debug only) | Django secret key |
| `DEBUG` | no | `False` | Enable debug mode |
| `DATABASE_URL` | no | `sqlite:///db.sqlite3` | Database connection string |
| `LOCAL_DATABASE_URL` | no | `DATABASE_URL` | Local database alias used by sync commands |
| `RENDER_DATABASE_URL` | sync | | Render database alias used by sync commands |
| `ALLOWED_HOSTS_EXTRA` | no | | Comma-separated extra allowed hosts |
| `CSRF_TRUSTED_ORIGINS_EXTRA` | no | | Comma-separated extra CSRF origins |
| `EMAIL_HOST_USER` | yes (email) | | SMTP username |
| `EMAIL_HOST_PASSWORD` | yes (email) | | SMTP password |
| `PASSWORD_SETUP_DEEP_LINK_BASE` | no | render URL | Base URL for player invite deep links |
| `AI_ASSISTANT_ENABLED` | no | `False` | Enable the AI assistant endpoint |
| `AI_PROVIDER` | no | `ollama` | AI backend provider for `/api/ai/chat/`; use `ollama` locally or `gemini` with a server-side key |
| `OLLAMA_BASE_URL` | no | `http://localhost:11434` | Local Ollama server base URL |
| `OLLAMA_CHAT_MODEL` | no | `qwen3:4b` | Primary local Ollama chat model |
| `OLLAMA_FALLBACK_MODEL` | no | `llama3.2:3b` | Fallback local Ollama chat model |
| `OLLAMA_NUM_PREDICT` | no | `220` | Maximum local Ollama response tokens for one assistant answer |
| `AI_RESPONSE_TEMPERATURE` | no | `0` | Generation temperature; keep at `0` for more repeatable answers |
| `AI_RANDOM_SEED` | no | `7` | Ollama seed used to reduce repeated-answer drift |
| `GEMINI_API_KEY` | Gemini only | | Server-side Gemini API key; never send this to mobile |
| `GEMINI_MODEL` | no | `gemini-2.5-flash` | Primary Gemini model |
| `GEMINI_FALLBACK_MODEL` | no | `gemini-2.5-flash-lite` | Fallback Gemini model |
| `AI_MAX_CONTEXT_DAYS` | no | `14` | Default recent backend data window |
| `AI_MAX_HISTORY_MESSAGES` | no | `8` | Maximum recent user/assistant messages included for follow-up questions |
| `AI_CONVERSATION_CACHE_TTL_SECONDS` | no | `1800` | Per-user server-side follow-up memory TTL when the client does not send history |

## Local AI Assistant

For local development with Ollama, add these values to your local environment:

```env
AI_ASSISTANT_ENABLED=True
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen3:4b
OLLAMA_FALLBACK_MODEL=llama3.2:3b
OLLAMA_NUM_PREDICT=220
AI_RESPONSE_TEMPERATURE=0
AI_RANDOM_SEED=7
AI_MAX_CONTEXT_DAYS=14
AI_MAX_HISTORY_MESSAGES=8
AI_CONVERSATION_CACHE_TTL_SECONDS=1800
```

The mobile app calls Django only. Django authenticates the user, routes the question to safe backend data sources,
and builds compact facts from existing models/services. Clear factual questions such as profile/account fields,
today's sessions, latest sessions, attendance summaries, readiness check-ins, and attention reasons are answered
directly by Django for lower latency; other backend-data questions call the configured server-side AI provider. General
questions are blocked before the model is called and return:

```json
{
  "answer": "I can only help with information related to your XpertForma backend data, such as profiles, sessions, attendance, performance, readiness, progress, plans, players, and coach insights.",
  "cards": [],
  "actions": [],
  "suggested_questions": [
    "What is my latest session?",
    "How is my weekly progress?",
    "Show my attendance summary"
  ]
}
```

Manual test after logging in and sending the JWT access token:

```http
POST http://127.0.0.1:8000/api/ai/chat/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "What is my latest session?",
  "screen": "PLAYER_HOME",
  "selected_player_id": null,
  "history": []
}
```

Player weekly count example:

```http
POST http://127.0.0.1:8000/api/ai/chat/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "How many sessions did I complete this week?",
  "screen": "PLAYER_PROGRESS",
  "selected_player_id": null,
  "history": []
}
```

Coach selected-player example:

```http
POST http://127.0.0.1:8000/api/ai/chat/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "What is this player's attendance this month?",
  "screen": "COACH_PLAYER_PROFILE",
  "selected_player_id": "<player_uuid>",
  "history": []
}
```

Follow-up example. The client can send recent turns, or Django will remember a few recent turns per authenticated user
for `AI_CONVERSATION_CACHE_TTL_SECONDS`.

```http
POST http://127.0.0.1:8000/api/ai/chat/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "why?",
  "screen": "COACH_PLAYER_PROFILE",
  "selected_player_id": "<player_uuid>",
  "history": [
    {
      "role": "user",
      "content": "Why does this player need attention?"
    },
    {
      "role": "assistant",
      "content": "This player needs attention because he missed the latest session."
    }
  ]
}
```

## Running Tests

```bash
python manage.py test
```

## Sync Local and Render Data

Set `RENDER_DATABASE_URL` in your local `.env` to the Render external database URL. If
your regular `DATABASE_URL` does not point at your local database, also set
`LOCAL_DATABASE_URL`.

Preview both database counts without changing data:

```bash
python manage.py admin_database_sync
```

Copy additions and edits both ways:

```bash
python manage.py admin_database_sync --apply
```

The sync command does not delete records from either database. If the same primary
key was edited in both places, Render wins by default; use
`--conflict-winner local` to prefer local values. JSON backups are written to
`local_db_backups/` before changes are applied.

## API Reference

Start the server and visit `/api-reference/` for the full interactive API documentation.

## Project Structure

```
accounts/          User, Coach, Player, Admin models and API
training/          Training plans, sessions, player progress
organizations/     Club and Team models
website/           Server-rendered admin panel and public pages
xpertforma_platform/  Django project settings and root URL config
```
