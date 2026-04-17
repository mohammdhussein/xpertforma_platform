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
| `ALLOWED_HOSTS_EXTRA` | no | | Comma-separated extra allowed hosts |
| `CSRF_TRUSTED_ORIGINS_EXTRA` | no | | Comma-separated extra CSRF origins |
| `EMAIL_HOST_USER` | yes (email) | | SMTP username |
| `EMAIL_HOST_PASSWORD` | yes (email) | | SMTP password |
| `PASSWORD_SETUP_DEEP_LINK_BASE` | no | render URL | Base URL for player invite deep links |

## Running Tests

```bash
python manage.py test
```

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
