import re

from ai_assistant.services.backend_scope_guard import is_backend_data_question
from ai_assistant.services.data_catalog import (
    DATA_ADMIN,
    DATA_ATTENDANCE,
    DATA_CHECKINS,
    DATA_COACHES,
    DATA_DASHBOARD,
    DATA_ORGANIZATIONS,
    DATA_PERFORMANCE,
    DATA_PLANS,
    DATA_PLAYERS,
    DATA_POSITIONS,
    DATA_PROFILE,
    DATA_SESSIONS,
)


def route_backend_data_question(message: str, screen: str | None = None) -> dict:
    normalized = _normalize(message)
    tokens = set(_tokenize(normalized))
    is_related = is_backend_data_question(message, screen)
    sources = _detect_data_sources(normalized, tokens, screen)

    if not sources and is_related:
        sources = [DATA_PROFILE]

    return {
        "is_backend_related": is_related and bool(sources),
        "data_sources": sources,
        "time_range": _detect_time_range(normalized, tokens),
        "target": _detect_target(normalized, tokens, screen),
        "question_type": _detect_question_type(normalized, tokens),
    }


def _detect_data_sources(normalized, tokens, screen):
    sources = []

    if tokens & {"me", "my", "profile", "account", "height", "weight", "foot", "status", "state"}:
        sources.append(DATA_PROFILE)
    if tokens & {"player", "players", "roster", "teammates", "team"}:
        sources.append(DATA_PLAYERS)
    if tokens & {"coach", "coaches"}:
        sources.append(DATA_COACHES)
    if tokens & {"session", "sessions", "training", "schedule", "latest", "upcoming", "completed", "missed"}:
        sources.append(DATA_SESSIONS)
    if tokens & {"attendance", "attended", "attendant", "present", "late", "missed", "absent", "absence", "complete", "completed"}:
        sources.append(DATA_ATTENDANCE)
    if tokens & {
        "performance",
        "progress",
        "score",
        "effort",
        "consistency",
        "streak",
        "speed",
        "stamina",
        "strength",
        "skills",
        "focus",
        "load",
    }:
        sources.append(DATA_PERFORMANCE)
    if tokens & {
        "readiness",
        "recovery",
        "checkin",
        "checkins",
        "sleep",
        "mood",
        "sore",
        "soreness",
        "zones",
        "injury",
        "injured",
        "pain",
    }:
        sources.append(DATA_CHECKINS)
    if tokens & {"plan", "plans", "assigned", "assignment"} or "training plan" in normalized:
        sources.append(DATA_PLANS)
    if tokens & {"dashboard", "alert", "alerts", "attention", "risk", "overview", "insight", "insights"}:
        sources.append(DATA_DASHBOARD)
        if tokens & {"attention", "risk", "alert", "alerts"}:
            sources.extend([DATA_PLAYERS, DATA_PERFORMANCE, DATA_ATTENDANCE, DATA_CHECKINS])
    if tokens & {"position", "positions", "role", "roles"}:
        sources.append(DATA_POSITIONS)
    if tokens & {"club", "clubs", "organization", "organizations", "team", "teams"}:
        sources.append(DATA_ORGANIZATIONS)
    if tokens & {"admin", "staff", "pending", "request", "requests", "approval", "approve", "rejected"}:
        sources.append(DATA_ADMIN)

    screen_value = str(screen or "").upper()
    if not sources:
        if screen_value.startswith("COACH_DASHBOARD"):
            sources.extend([DATA_DASHBOARD, DATA_PLAYERS])
        elif screen_value.startswith("COACH_PLAYER"):
            sources.append(DATA_PLAYERS)
        elif screen_value.startswith("PLAYER_PROGRESS"):
            sources.extend([DATA_PERFORMANCE, DATA_CHECKINS, DATA_ATTENDANCE])
        elif screen_value.startswith("PLAYER_HOME"):
            sources.extend([DATA_PROFILE, DATA_SESSIONS, DATA_CHECKINS])
        elif screen_value.startswith("ADMIN_"):
            sources.append(DATA_ADMIN)

    return _dedupe(sources)


def _detect_time_range(normalized, tokens):
    if tokens & {"latest", "last", "current"}:
        return {"type": "latest"}
    if "this week" in normalized or tokens & {"week", "weekly"}:
        return {"type": "week", "days": 7}
    if "this month" in normalized or tokens & {"month", "monthly"}:
        return {"type": "month", "days": 30}
    if tokens & {"today"}:
        return {"type": "today", "days": 1}
    if tokens & {"yesterday"}:
        return {"type": "yesterday", "days": 1}
    if tokens & {"recent", "history"}:
        return {"type": "recent"}
    return {"type": "default"}


def _detect_target(normalized, tokens, screen):
    screen_value = str(screen or "").upper()
    name_hint = _extract_name_hint(normalized)
    if screen_value.startswith("PLAYER_") or tokens & {"me", "my", "mine"}:
        return {"type": "self", "selected_player_id_required": False, "name_hint": None}
    if "this player" in normalized or screen_value.startswith("COACH_PLAYER"):
        return {
            "type": "selected_player",
            "selected_player_id_required": screen_value.startswith("COACH_PLAYER"),
            "name_hint": name_hint,
        }
    if name_hint and _looks_like_named_player_question(normalized):
        return {"type": "selected_player", "selected_player_id_required": False, "name_hint": name_hint}
    if tokens & {"team", "players", "roster", "who", "which"} or screen_value.startswith("COACH_DASHBOARD"):
        return {"type": "team", "selected_player_id_required": False, "name_hint": None}
    return {"type": "self", "selected_player_id_required": False, "name_hint": None}


def _detect_question_type(normalized, tokens):
    if tokens & {"latest", "last", "current"}:
        return "latest"
    if "how many" in normalized or tokens & {"count", "number", "many"}:
        return "count"
    if tokens & {"who", "which", "list", "show"}:
        return "list"
    if tokens & {"best", "worst", "most", "least", "highest", "lowest"}:
        return "comparison"
    if tokens & {"why", "explain", "reason", "because"}:
        return "explanation"
    if tokens & {"status", "state", "injured", "active"}:
        return "status"
    return "summary"


def _looks_like_named_player_question(normalized):
    return bool(_extract_name_hint(normalized))


def _extract_name_hint(normalized):
    possessive_match = re.search(r"\b([a-z][a-z0-9]*(?:\s+[a-z][a-z0-9]*){0,2})'s\b", normalized)
    if possessive_match:
        return possessive_match.group(1)

    subject_hint = _extract_named_subject_hint(_tokenize(normalized))
    if subject_hint:
        return subject_hint

    this_player_prefixes = ["what is", "why is", "how is", "show", "tell me about"]
    for prefix in this_player_prefixes:
        if normalized.startswith(prefix):
            remainder = normalized[len(prefix):].strip()
            tokens = [
                token
                for token in _tokenize(remainder)
                if token not in {
                    "this",
                    "player",
                    "attendance",
                    "readiness",
                    "progress",
                    "performance",
                    "status",
                    "the",
                    "latest",
                    "last",
                    "current",
                    "session",
                    "sessions",
                    "training",
                    "plan",
                    "plans",
                    "today",
                    "week",
                    "month",
                }
            ]
            if tokens:
                return " ".join(tokens[:3])
    return None


def _extract_named_subject_hint(tokens):
    subject_starters = {"about", "check", "does", "did", "dose", "has", "have", "is", "show", "was"}
    ignored_tokens = {
        "assistant",
        "because",
        "explain",
        "how",
        "me",
        "please",
        "tell",
        "the",
        "user",
        "what",
        "when",
        "where",
        "why",
    }
    name_stoppers = {
        "active",
        "attendance",
        "attention",
        "checkin",
        "checkins",
        "completed",
        "dashboard",
        "data",
        "has",
        "have",
        "injured",
        "late",
        "latest",
        "missed",
        "month",
        "need",
        "needs",
        "performance",
        "plan",
        "plans",
        "player",
        "players",
        "progress",
        "readiness",
        "recovery",
        "session",
        "sessions",
        "status",
        "summary",
        "team",
        "today",
        "training",
        "week",
    }

    for index, token in enumerate(tokens):
        if token not in subject_starters:
            continue
        candidate = []
        for next_token in tokens[index + 1:]:
            if next_token in ignored_tokens:
                continue
            if next_token in name_stoppers:
                break
            candidate.append(next_token)
            if len(candidate) == 3:
                break
        candidate = [token for token in candidate if token not in {"a", "an", "my", "this"}]
        if candidate:
            return " ".join(candidate)
    return None


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _tokenize(value):
    return re.findall(r"[a-z0-9]+", value)


def _dedupe(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
