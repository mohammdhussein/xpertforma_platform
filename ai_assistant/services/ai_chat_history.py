import re

from django.conf import settings
from django.core.cache import cache

from ai_assistant.services.backend_scope_guard import BLOCKED_KEYWORDS


VALID_HISTORY_ROLES = {"user", "assistant"}
FOLLOW_UP_TOKENS = {
    "he",
    "her",
    "him",
    "his",
    "it",
    "she",
    "that",
    "their",
    "them",
    "they",
    "this",
}
VAGUE_FOLLOW_UP_TOKENS = {"how", "what", "when", "where", "which", "who", "why"}


def normalize_chat_history(history, *, max_messages=None):
    limit = max_messages if max_messages is not None else _max_history_messages()
    normalized = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role not in VALID_HISTORY_ROLES or not content:
            continue
        normalized.append({"role": role, "content": content[:2000]})
    return normalized[-limit:]


def get_cached_chat_history(user):
    return normalize_chat_history(cache.get(_cache_key(user), []))


def remember_chat_turn(user, history, *, user_message, assistant_answer):
    next_history = [
        *normalize_chat_history(history),
        {"role": "user", "content": str(user_message or "").strip()[:2000]},
        {"role": "assistant", "content": str(assistant_answer or "").strip()[:2000]},
    ]
    next_history = normalize_chat_history(next_history)
    cache.set(_cache_key(user), next_history, _history_ttl_seconds())
    return next_history


def conversation_scope_text(message, history):
    parts = [
        f"{item['role']}: {item['content']}"
        for item in normalize_chat_history(history)
    ]
    parts.append(f"user: {message}")
    return "\n".join(parts)


def should_route_with_history(message, history):
    if not normalize_chat_history(history):
        return False
    tokens = _tokenize(message)
    if not tokens or len(tokens) > 12:
        return False
    if set(tokens) & BLOCKED_KEYWORDS:
        return False
    token_set = set(tokens)
    if token_set & FOLLOW_UP_TOKENS:
        return True
    return len(tokens) <= 3 and bool(token_set & VAGUE_FOLLOW_UP_TOKENS)


def format_chat_history_for_prompt(history):
    normalized = normalize_chat_history(history)
    if not normalized:
        return ""
    return "\n".join(
        f"{item['role'].upper()}: {item['content']}"
        for item in normalized
    )


def _cache_key(user):
    return f"ai_assistant:chat_history:{user.pk}"


def _max_history_messages():
    return max(int(getattr(settings, "AI_MAX_HISTORY_MESSAGES", 8)), 0)


def _history_ttl_seconds():
    return max(int(getattr(settings, "AI_CONVERSATION_CACHE_TTL_SECONDS", 1800)), 0)


def _tokenize(value):
    return re.findall(r"[a-z0-9]+", str(value or "").lower())
