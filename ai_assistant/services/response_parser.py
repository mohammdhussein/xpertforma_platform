import json
import re


DEFAULT_SUGGESTED_QUESTIONS = [
    "What is my latest session?",
    "How is my weekly progress?",
    "Show my attendance summary",
]
SAFE_FALLBACK_ANSWER = "I couldn't generate a clean assistant response. Please try again."
VALID_CARD_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}
REQUIRED_RESPONSE_KEYS = {"answer", "cards", "actions", "suggested_questions"}
CONTEXT_LEAK_MARKERS = [
    '"team_overview"',
    '"players_overview"',
    '"selected_player"',
    '"player_profile"',
    '"latest_readiness"',
    '"recent_checkins"',
    '"weekly_progress"',
    '"readiness_summary_14d"',
    '"session_summary"',
    '"players_summary"',
    '"user"',
    "CONTEXT_DATA",
]
THINKING_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def parse_ai_response(raw_content):
    content = strip_thinking(raw_content)
    parsed = _parse_json_object(content)
    if _is_response_object(parsed):
        return _normalize_response(parsed)
    return _fallback_response(content)


def strip_thinking(value):
    content = "" if value is None else str(value)
    stripped = THINKING_PATTERN.sub("", content).strip()
    dangling_close_tag = "</think>"
    if dangling_close_tag in stripped.lower():
        close_index = stripped.lower().rfind(dangling_close_tag)
        stripped = stripped[close_index + len(dangling_close_tag):]
    return stripped.strip()


def _parse_json_object(content):
    for candidate in _json_candidates(content):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _json_candidates(content):
    stripped = _strip_code_fence(content)
    yield stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and start < end:
        yield stripped[start:end + 1]


def _strip_code_fence(content):
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _normalize_response(data):
    nested_response = _parse_json_object(str(data.get("answer") or ""))
    if _is_response_object(nested_response):
        return _normalize_response(nested_response)

    return {
        "answer": str(data.get("answer") or ""),
        "cards": _normalize_cards(data.get("cards")),
        "actions": _normalize_actions(data.get("actions")),
        "suggested_questions": _normalize_suggested_questions(data.get("suggested_questions")),
    }


def _normalize_cards(value):
    if not isinstance(value, list):
        return []
    cards = []
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "INFO").upper()
        cards.append(
            {
                "title": str(item.get("title") or ""),
                "value": str(item.get("value") or ""),
                "severity": severity if severity in VALID_CARD_SEVERITIES else "INFO",
            }
        )
    return cards


def _normalize_actions(value):
    if not isinstance(value, list):
        return []
    actions = []
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        payload = item.get("payload")
        actions.append(
            {
                "label": str(item.get("label") or ""),
                "type": str(item.get("type") or ""),
                "payload": payload if isinstance(payload, dict) else {},
            }
        )
    return actions


def _normalize_suggested_questions(value):
    if not isinstance(value, list):
        return DEFAULT_SUGGESTED_QUESTIONS
    questions = [str(item) for item in value if str(item).strip()]
    return (questions or DEFAULT_SUGGESTED_QUESTIONS)[:3]


def _fallback_response(content):
    partial_answer = _extract_partial_answer(content)
    return {
        "answer": _build_fallback_answer(content, partial_answer),
        "cards": [],
        "actions": [],
        "suggested_questions": DEFAULT_SUGGESTED_QUESTIONS,
    }


def _is_response_object(value):
    if not isinstance(value, dict):
        return False
    return REQUIRED_RESPONSE_KEYS.issubset(value.keys())


def _looks_like_context_leak(content):
    if not content:
        return False
    upper_content = content.upper()
    return any(marker.upper() in upper_content for marker in CONTEXT_LEAK_MARKERS)


def _build_fallback_answer(content, partial_answer):
    if partial_answer:
        return partial_answer
    if _looks_like_context_leak(content) or _looks_like_broken_json(content):
        return SAFE_FALLBACK_ANSWER
    return content


def _extract_partial_answer(content):
    match = re.search(r'"answer"\s*:\s*"((?:\\.|[^"\\])*)"', content or "", re.DOTALL)
    if not match:
        return None
    encoded = f'"{match.group(1)}"'
    try:
        answer = json.loads(encoded)
    except json.JSONDecodeError:
        answer = match.group(1)
    cleaned = strip_thinking(answer).strip()
    if _looks_like_broken_json(cleaned) or _looks_like_context_leak(cleaned):
        nested_answer = _extract_partial_answer(cleaned)
        return nested_answer or None
    return cleaned or None


def _looks_like_broken_json(content):
    stripped = str(content or "").strip()
    if not stripped:
        return False
    return stripped.startswith("{") or stripped.startswith("[") or '"answer"' in stripped
