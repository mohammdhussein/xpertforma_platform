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
| `GROQ_API_KEY` | AI assistant | | Server-side Groq API key; never send this to mobile |
| `GROQ_BASE_URL` | no | `https://api.groq.com/openai/v1` | Groq OpenAI-compatible API base URL |
| `GROQ_MODEL` | no | `llama-3.3-70b-versatile` | Primary Groq chat model |
| `GROQ_FALLBACK_MODEL` | no | `openai/gpt-oss-20b` | Fallback Groq chat model |
| `AI_RESPONSE_TEMPERATURE` | no | `0.2` | Generation temperature |
| `AI_RANDOM_SEED` | no | `7` | Groq seed used to reduce repeated-answer drift |
| `AI_MAX_CONTEXT_DAYS` | no | `14` | Default recent backend data window |
| `AI_CONVERSATION_CACHE_TTL_SECONDS` | no | `1800` | Server-side AI plan draft TTL |

## Local AI Assistant

For local development with Groq, add these values to your local environment:

```env
AI_ASSISTANT_ENABLED=True
GROQ_API_KEY=your_groq_api_key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
AI_RESPONSE_TEMPERATURE=0.2
AI_RANDOM_SEED=7
AI_MAX_CONTEXT_DAYS=14
AI_CONVERSATION_CACHE_TTL_SECONDS=1800
```

The mobile app calls Django only. Django authenticates the user, rejects unsupported client-supplied identity/context
fields, routes safe backend-data questions to permission-scoped Django context, and answers clear factual questions
directly when possible. Questions that need language generation call Groq server-side. Coach plan requests resolve
player names from the signed-in coach's roster, ask Groq for 1 to 5 structured JSON plan options, validate and repair
the JSON when needed, store a server-side draft, render sanitized HTML, and return native app actions for confirmation.

Manual test after logging in and sending the JWT access token:

```http
POST http://127.0.0.1:8000/api/ai/chat/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "What is my latest session?",
  "response_format": "html"
}
```

Player weekly count example:

```http
POST http://127.0.0.1:8000/api/ai/chat/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "How many sessions did I complete this week?",
  "response_format": "html"
}
```

Coach selected-player example:

```http
POST http://127.0.0.1:8000/api/ai/chat/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "message": "Suggest 2 training plans for Ahmad Saleh",
  "response_format": "html"
}
```

Plan requests can ask for 1 to 5 plan options. If no count is included, Django defaults to 3 options. The HTML is only
for display; the mobile app should render native buttons from the `actions` array.

Plan confirmation example:

```http
POST http://127.0.0.1:8000/api/ai/actions/confirm/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "action_type": "select_plan_option",
  "draft_id": "<draft_uuid>",
  "option_id": "option_1"
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
