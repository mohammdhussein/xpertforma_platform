import re

from ai_assistant.services.data_catalog import get_catalog_keywords


BACKEND_BLOCKED_RESPONSE = {
    "answer": (
        "I can only help with information related to your XpertForma backend data, "
        "such as profiles, sessions, attendance, performance, readiness, progress, "
        "plans, players, and coach insights."
    ),
    "cards": [],
    "actions": [],
    "suggested_questions": [
        "What is my latest session?",
        "How is my weekly progress?",
        "Show my attendance summary",
    ],
}

BLOCKED_PHRASES = {
    "tell me a joke",
    "write code",
    "write python",
    "python code",
    "javascript code",
    "general programming",
    "school essay",
    "write an essay",
    "translate this",
    "translate to",
    "capital of",
    "weather today",
    "latest news",
    "news today",
    "movie recommendation",
    "song lyrics",
    "recipe for",
}

BLOCKED_KEYWORDS = {
    "joke",
    "politics",
    "history",
    "weather",
    "news",
    "recipe",
    "movie",
    "song",
    "lyrics",
    "programming",
    "django",
    "serializer",
    "python",
    "javascript",
    "code",
    "essay",
    "translation",
    "translate",
    "capital",
    "president",
    "election",
    "stock",
    "bitcoin",
    "algebra",
    "calculus",
}

STRONG_BACKEND_KEYWORDS = {
    "xpertforma",
    "backend",
    "profile",
    "player",
    "players",
    "coach",
    "coaches",
    "session",
    "sessions",
    "attendance",
    "performance",
    "readiness",
    "recovery",
    "progress",
    "checkin",
    "checkins",
    "dashboard",
    "alert",
    "alerts",
    "plan",
    "plans",
    "position",
    "positions",
    "team",
    "teams",
    "upcoming",
    "latest",
    "scheduled",
    "schedule",
    "date",
    "today",
    "tomorrow",
}


def is_backend_data_question(message: str, screen: str | None = None) -> bool:
    normalized = _normalize(message)
    tokens = set(_tokenize(normalized))

    if not normalized:
        return False
    if _has_blocked_phrase(normalized):
        return False

    blocked_signal = bool(tokens & BLOCKED_KEYWORDS)
    backend_signal = bool(tokens & get_catalog_keywords())
    strong_backend_signal = bool(tokens & STRONG_BACKEND_KEYWORDS)
    screen_signal = _is_app_screen(screen)

    if blocked_signal and not strong_backend_signal:
        return False
    if backend_signal:
        return True
    if screen_signal and not blocked_signal:
        return True
    return False


def _has_blocked_phrase(normalized):
    return any(phrase in normalized for phrase in BLOCKED_PHRASES)


def _is_app_screen(screen):
    value = str(screen or "").strip().upper()
    return value.startswith("PLAYER_") or value.startswith("COACH_") or value.startswith("ADMIN_")


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _tokenize(value):
    return re.findall(r"[a-z0-9]+", value)
