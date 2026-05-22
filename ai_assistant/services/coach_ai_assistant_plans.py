import json
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from rest_framework import serializers

from ai_assistant.models import AIPlanDraft
from ai_assistant.services.coach_ai_assistant_groq import GroqChatClient
from ai_assistant.services.coach_ai_assistant_players import build_player_context
from training.services.coach_training_plans import create_coach_training_plan
from training.statuses import Intensity, VALID_TRAINING_SESSION_TYPES


PLAN_OPTION_COUNT = 3
VALID_INTENSITIES = set(Intensity.values)


class AIPlanInvalidResponse(Exception):
    pass


class AIPlanDraftExpired(Exception):
    pass


class AIPlanDraftPermissionDenied(Exception):
    pass


class AIPlanInvalidSelection(Exception):
    pass


def is_plan_suggestion_request(message):
    normalized = (message or "").lower()
    has_plan_word = bool(re.search(r"\b(plan|plans|program|programs|training plan)\b", normalized))
    has_action_word = bool(re.search(r"\b(suggest|create|generate|build|recommend|prepare|make)\b", normalized))
    return has_plan_word and has_action_word


def parse_requested_plan_date_range(message):
    text = re.sub(r"\s+", " ", (message or "").lower()).strip()
    if not text:
        return None

    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    today_pattern = r"(?:today|current\s+day)"
    tomorrow_pattern = r"(?:tomorrow(?:\s+day)?)"

    start_date = None
    end_date = None

    if re.search(
        rf"\b(?:to\s+)?(?:start|starts|starting|begin|begins|beginning)\s+"
        rf"(?:from|on|in|at)?\s*(?:the\s+)?{today_pattern}\b",
        text,
    ) or re.search(rf"\bfrom\s+(?:the\s+)?{today_pattern}\b", text):
        start_date = today
    elif re.search(
        rf"\b(?:to\s+)?(?:start|starts|starting|begin|begins|beginning)\s+"
        rf"(?:from|on|in|at)?\s*(?:the\s+)?{tomorrow_pattern}\b",
        text,
    ) or re.search(rf"\bfrom\s+(?:the\s+)?{tomorrow_pattern}\b", text):
        start_date = tomorrow

    if re.search(
        rf"\b(?:to\s+)?(?:end|ends|ending|finish|finishes|finishing)\s+"
        rf"(?:in|on|by|at)?\s*(?:the\s+)?{tomorrow_pattern}\b",
        text,
    ) or re.search(rf"\b(?:until|through|to)\s+(?:the\s+)?{tomorrow_pattern}\b", text):
        end_date = tomorrow
    elif re.search(
        rf"\b(?:to\s+)?(?:end|ends|ending|finish|finishes|finishing)\s+"
        rf"(?:in|on|by|at)?\s*(?:the\s+)?{today_pattern}\b",
        text,
    ) or re.search(rf"\b(?:until|through|to)\s+(?:the\s+)?{today_pattern}\b", text):
        end_date = today

    if start_date is None and end_date is None:
        return None

    if start_date is None:
        start_date = today if end_date > today else today - timedelta(days=1)
    if end_date is not None and end_date <= start_date:
        raise AIPlanInvalidResponse("Requested plan end date must be after start date.")

    return {"start_date": start_date, "end_date": end_date}


def generate_plan_options_for_player(*, coach_user, player_profile):
    return generate_plan_options_for_players(coach_user=coach_user, player_profiles=[player_profile])


def generate_plan_options_for_players(*, coach_user, player_profiles, requested_date_range=None):
    player_context = [build_player_context(profile) for profile in player_profiles]
    today = timezone.localdate()
    requested_date_range = requested_date_range or {}
    start_date = requested_date_range.get("start_date") or today + timedelta(days=1)
    end_date = requested_date_range.get("end_date")
    system_prompt, user_prompt = build_plan_generation_prompts(
        coach_user=coach_user,
        player_context=player_context,
        start_date=start_date,
        end_date=end_date,
    )
    client = GroqChatClient()
    raw_content = client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        options = parse_plan_options(raw_content, start_date=start_date, end_date=end_date)
    except AIPlanInvalidResponse as exc:
        repair_system_prompt, repair_user_prompt = build_plan_repair_prompts(
            player_context=player_context,
            start_date=start_date,
            end_date=end_date,
            invalid_content=raw_content,
            validation_error=str(exc),
        )
        raw_content = client.chat_json(system_prompt=repair_system_prompt, user_prompt=repair_user_prompt)
        options = parse_plan_options(raw_content, start_date=start_date, end_date=end_date)

    draft = save_plan_draft(
        coach_user=coach_user,
        players=[profile.user for profile in player_profiles],
        options=options,
    )
    return draft, options


def build_plan_generation_prompts(*, coach_user, player_context, start_date, end_date=None):
    option_count = int(getattr(settings, "AI_PLAN_OPTIONS_COUNT", PLAN_OPTION_COUNT))
    date_rules = [f"Every option must start on {start_date.isoformat()}."]
    prompt_dates = {"plan_start_date": start_date.isoformat()}
    if end_date is not None:
        date_rules.extend(
            [
                f"Every option must end on {end_date.isoformat()}.",
                f"Use a duration of {_inclusive_days(start_date, end_date)} days.",
                "Every preview session must be inside this requested start/end date range.",
            ]
        )
        prompt_dates["plan_end_date"] = end_date.isoformat()

    system_prompt = (
        "You are XpertForma's coach assistant. Return structured JSON only. "
        "Do not return HTML, Markdown, prose, JavaScript, buttons, or explanations. "
        "All session_type values must be GROUP, TEAM, or INDIVIDUAL. "
        "All intensity values must be LOW, MEDIUM, or HIGH."
    )
    user_prompt = json.dumps(
        {
            "task": f"Suggest exactly {option_count} training plan options for the coach's selected player or players.",
            "response_schema": {
                "options": [
                    {
                        "option_id": "option_1",
                        "title": "string",
                        "description": "string",
                        "duration": "string such as '7 days'",
                        "difficulty": "string",
                        "focus_areas": ["string"],
                        "sessions_count": "integer",
                        "preview_sessions": [
                            {
                                "title": "string",
                                "day_label": "Day 1",
                                "session_type": "GROUP",
                                "start_time": "HH:MM",
                                "end_time": "HH:MM",
                                "intensity": "MEDIUM",
                                "location": "string",
                                "notes": "string",
                            }
                        ],
                    }
                ]
            },
            "rules": [
                f"Return exactly {option_count} options.",
                "Use option_id values option_1, option_2, and option_3.",
                "Use only realistic football training content.",
                "If multiple players are provided, make the plan suitable for all selected players together.",
                "Keep preview_sessions concise but sufficient to create the plan.",
                "Do not include selected_player_id, screen_context, user_id, coach_id, role, html, or player_id.",
                *date_rules,
            ],
            **prompt_dates,
            "coach": {"id": str(coach_user.id), "name": coach_user.name},
            "players": player_context,
        },
        ensure_ascii=True,
    )
    return system_prompt, user_prompt


def build_plan_repair_prompts(*, player_context, start_date, invalid_content, validation_error, end_date=None):
    option_count = int(getattr(settings, "AI_PLAN_OPTIONS_COUNT", PLAN_OPTION_COUNT))
    prompt_dates = {"plan_start_date": start_date.isoformat()}
    if end_date is not None:
        prompt_dates["plan_end_date"] = end_date.isoformat()
    system_prompt = (
        "You repair invalid XpertForma plan JSON. Return JSON only. "
        "No prose, no HTML, no Markdown, no code fences. "
        f"The top-level object must contain an options array with exactly {option_count} objects."
    )
    user_prompt = json.dumps(
        {
            "validation_error": validation_error,
            "invalid_response": invalid_content[:6000],
            "required_shape": _plan_response_shape(),
            "required_option_ids": ["option_1", "option_2", "option_3"],
            **prompt_dates,
            "players": player_context,
            "hard_rules": [
                f"Return exactly {option_count} options, no more and no fewer.",
                "Every option must include option_id, title, description, duration, difficulty, focus_areas, sessions_count, and preview_sessions.",
                "Every preview session must include title, day_label, session_type, start_time, end_time, intensity, location, and notes.",
                "session_type must be GROUP, TEAM, or INDIVIDUAL.",
                "intensity must be LOW, MEDIUM, or HIGH.",
                *(
                    [
                        f"Every option must end on {end_date.isoformat()}.",
                        "Every preview session must be inside the requested start/end date range.",
                    ]
                    if end_date is not None
                    else []
                ),
            ],
        },
        ensure_ascii=True,
    )
    return system_prompt, user_prompt


def parse_plan_options(raw_content, *, start_date, end_date=None):
    payload = _load_json_payload(raw_content)
    raw_options = None
    if isinstance(payload, dict):
        raw_options = (
            payload.get("options")
            or payload.get("plan_options")
            or payload.get("planOptions")
            or payload.get("plans")
            or payload.get("training_plans")
            or payload.get("trainingPlans")
        )
    if raw_options is None and isinstance(payload, list):
        raw_options = payload
    if not isinstance(raw_options, list):
        raise AIPlanInvalidResponse("Groq response must include an options array.")

    expected_count = int(getattr(settings, "AI_PLAN_OPTIONS_COUNT", PLAN_OPTION_COUNT))
    if len(raw_options) != expected_count:
        raise AIPlanInvalidResponse(f"Groq response must include exactly {expected_count} plan options.")

    normalized_options = []
    for index, raw_option in enumerate(raw_options, start=1):
        normalized_options.append(
            normalize_plan_option(
                raw_option,
                index=index,
                start_date=start_date,
                end_date=end_date,
            )
        )
    return normalized_options


def normalize_plan_option(raw_option, *, index, start_date, end_date=None):
    if not isinstance(raw_option, dict):
        raise AIPlanInvalidResponse("Each plan option must be an object.")

    duration_label = _required_text(raw_option, "duration")
    if end_date is None:
        duration_days = _parse_duration_days(duration_label)
        option_end_date = start_date + timedelta(days=duration_days - 1)
    else:
        if end_date <= start_date:
            raise AIPlanInvalidResponse("Plan end_date must be after start_date.")
        option_end_date = end_date
        duration_label = _format_duration_label(start_date=start_date, end_date=option_end_date)
    preview_sessions = raw_option.get("preview_sessions") or raw_option.get("previewSessions") or raw_option.get("sessions")
    if not isinstance(preview_sessions, list) or not preview_sessions:
        raise AIPlanInvalidResponse("Each plan option must include preview_sessions.")

    normalized_sessions = []
    for session_index, raw_session in enumerate(preview_sessions, start=1):
        normalized_sessions.append(
            normalize_preview_session(
                raw_session,
                index=session_index,
                start_date=start_date,
                end_date=option_end_date,
            )
        )

    sessions_count = _as_positive_int(raw_option.get("sessions_count"), field="sessions_count")
    if sessions_count != len(normalized_sessions):
        sessions_count = len(normalized_sessions)

    return {
        "option_id": f"option_{index}",
        "title": _required_text(raw_option, "title"),
        "description": _text_or_default(raw_option.get("description"), ""),
        "duration": duration_label,
        "difficulty": _required_text(raw_option, "difficulty"),
        "focus_areas": _normalize_focus_areas(raw_option),
        "sessions_count": sessions_count,
        "start_date": start_date.isoformat(),
        "end_date": option_end_date.isoformat(),
        "preview_sessions": normalized_sessions,
    }


def normalize_preview_session(raw_session, *, index, start_date, end_date):
    if not isinstance(raw_session, dict):
        raise AIPlanInvalidResponse("Each preview session must be an object.")

    session_type = _required_text(raw_session, "session_type").upper()
    if session_type not in VALID_TRAINING_SESSION_TYPES:
        raise AIPlanInvalidResponse("Invalid session_type in Groq response.")

    intensity = _required_text(raw_session, "intensity").upper()
    if intensity not in VALID_INTENSITIES:
        raise AIPlanInvalidResponse("Invalid intensity in Groq response.")

    start_time = _required_text(raw_session, "start_time")
    end_time = _required_text(raw_session, "end_time")
    parsed_start = parse_time(start_time)
    parsed_end = parse_time(end_time)
    if parsed_start is None or parsed_end is None:
        raise AIPlanInvalidResponse("Session times must use HH:MM format.")
    if parsed_end <= parsed_start:
        raise AIPlanInvalidResponse("Session end_time must be greater than start_time.")

    session_date = _date_for_session(raw_session.get("day_label"), index=index, start_date=start_date)
    if session_date < start_date or session_date > end_date:
        raise AIPlanInvalidResponse("Preview sessions must fit inside the plan date range.")

    return {
        "title": _required_text(raw_session, "title"),
        "day_label": _text_or_default(raw_session.get("day_label"), f"Day {index}"),
        "date": session_date.isoformat(),
        "session_type": session_type,
        "start_time": start_time,
        "end_time": end_time,
        "intensity": intensity,
        "location": _text_or_default(raw_session.get("location"), ""),
        "notes": _text_or_default(raw_session.get("notes"), ""),
    }


def save_plan_draft(*, coach_user, players, options):
    if not players:
        raise AIPlanInvalidResponse("At least one target player is required.")
    ttl_seconds = int(getattr(settings, "AI_CONVERSATION_CACHE_TTL_SECONDS", 1800))
    draft = AIPlanDraft.objects.create(
        coach=coach_user,
        player=players[0],
        options=options,
        expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
    )
    draft.target_players.set(players)
    return draft


def create_training_plan_from_draft_option(*, coach_user, draft_id, selected_option_id):
    try:
        draft = (
            AIPlanDraft.objects
            .select_related("coach", "player", "player__player_profile")
            .prefetch_related("target_players", "target_players__player_profile")
            .get(draft_id=draft_id)
        )
    except AIPlanDraft.DoesNotExist as exc:
        raise AIPlanInvalidSelection("Invalid selected option or draft.") from exc

    if draft.coach_id != coach_user.id:
        raise AIPlanDraftPermissionDenied("Permission denied for this draft.")
    if draft.expires_at <= timezone.now():
        raise AIPlanDraftExpired("Draft has expired.")
    target_players = list(draft.target_players.all()) or [draft.player]
    for player in target_players:
        if getattr(player, "player_profile", None) is None or player.player_profile.coach_id != coach_user.id:
            raise AIPlanDraftPermissionDenied("Player no longer belongs to this coach.")

    option = next(
        (item for item in draft.options if item.get("option_id") == selected_option_id),
        None,
    )
    if option is None:
        raise AIPlanInvalidSelection("Invalid selected option.")

    payload = build_plan_create_payload_from_option(
        option=option,
        player_ids=[player.id for player in target_players],
    )
    validate_plan_payload_before_save(payload)
    try:
        return create_coach_training_plan(coach_user=coach_user, payload=payload)
    except serializers.ValidationError as exc:
        raise serializers.ValidationError({"detail": "Validation failed.", "errors": exc.detail}) from exc


def build_plan_create_payload_from_option(*, option, player_ids):
    start_date = _required_text(option, "start_date")
    end_date = _required_text(option, "end_date")

    sessions = []
    for session in option.get("preview_sessions") or []:
        sessions.append(
            {
                "date": _required_text(session, "date"),
                "title": _required_text(session, "title"),
                "session_type": _required_text(session, "session_type"),
                "start_time": _required_text(session, "start_time"),
                "end_time": _required_text(session, "end_time"),
                "intensity": _required_text(session, "intensity"),
                "location": _text_or_default(session.get("location"), ""),
                "notes": _text_or_default(session.get("notes"), ""),
            }
        )

    return {
        "title": _required_text(option, "title"),
        "start_date": start_date,
        "end_date": end_date,
        "sessions": sessions,
        "assignee_players": [{"id": str(player_id)} for player_id in player_ids],
    }


def validate_plan_payload_before_save(payload):
    start_date = parse_date(payload.get("start_date") or "")
    end_date = parse_date(payload.get("end_date") or "")
    if start_date is None or end_date is None:
        raise serializers.ValidationError({"detail": "Validation failed.", "errors": {"date": "Invalid plan date."}})
    if end_date <= start_date:
        raise serializers.ValidationError(
            {"detail": "Validation failed.", "errors": {"end_date": "End date must be after start date."}}
        )

    for session in payload.get("sessions") or []:
        session_date = parse_date(session.get("date") or "")
        if session_date is None:
            raise serializers.ValidationError(
                {"detail": "Validation failed.", "errors": {"sessions": "Invalid session date."}}
            )
        if session_date < start_date or session_date > end_date:
            raise serializers.ValidationError(
                {"detail": "Validation failed.", "errors": {"sessions": "Session is outside plan date range."}}
            )

        if session.get("session_type") not in VALID_TRAINING_SESSION_TYPES:
            raise serializers.ValidationError(
                {"detail": "Validation failed.", "errors": {"session_type": "Invalid session_type."}}
            )
        if session.get("intensity") not in VALID_INTENSITIES:
            raise serializers.ValidationError(
                {"detail": "Validation failed.", "errors": {"intensity": "Invalid intensity."}}
            )

        start_time = parse_time(session.get("start_time") or "")
        end_time = parse_time(session.get("end_time") or "")
        if start_time is None or end_time is None:
            raise serializers.ValidationError(
                {"detail": "Validation failed.", "errors": {"time": "Invalid session time."}}
            )
        if end_time <= start_time:
            raise serializers.ValidationError(
                {"detail": "Validation failed.", "errors": {"end_time": "End time must be after start time."}}
            )


def _load_json_payload(raw_content):
    content = (raw_content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content)
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIPlanInvalidResponse("Groq returned invalid JSON.") from exc

    if not isinstance(payload, (dict, list)):
        raise AIPlanInvalidResponse("Groq response must be a JSON object.")
    return payload


def _normalize_focus_areas(raw_option):
    raw_focus_areas = (
        raw_option.get("focus_areas")
        or raw_option.get("focus areas")
        or raw_option.get("focusAreas")
        or []
    )
    if isinstance(raw_focus_areas, str):
        raw_focus_areas = [raw_focus_areas]
    if not isinstance(raw_focus_areas, list):
        raise AIPlanInvalidResponse("focus_areas must be a list.")
    focus_areas = [str(item).strip() for item in raw_focus_areas if str(item).strip()]
    if not focus_areas:
        raise AIPlanInvalidResponse("Each option must include at least one focus area.")
    return focus_areas[:5]


def _date_for_session(day_label, *, index, start_date):
    label = str(day_label or "")
    match = re.search(r"\bday\s*(\d+)\b", label, flags=re.IGNORECASE)
    offset = int(match.group(1)) - 1 if match else index - 1
    return start_date + timedelta(days=max(offset, 0))


def _parse_duration_days(value):
    if isinstance(value, int):
        days = value
    else:
        match = re.search(r"\d+", str(value or ""))
        days = int(match.group(0)) if match else 7
    if days < 2:
        raise AIPlanInvalidResponse("Plan duration must be at least 2 days.")
    return min(days, 31)


def _inclusive_days(start_date, end_date):
    return (end_date - start_date).days + 1


def _format_duration_label(*, start_date, end_date):
    days = _inclusive_days(start_date, end_date)
    return f"{days} day" if days == 1 else f"{days} days"


def _plan_response_shape():
    return {
        "options": [
            {
                "option_id": "option_1",
                "title": "string",
                "description": "string",
                "duration": "7 days",
                "difficulty": "Beginner|Intermediate|Advanced",
                "focus_areas": ["string"],
                "sessions_count": 3,
                "preview_sessions": [
                    {
                        "title": "string",
                        "day_label": "Day 1",
                        "session_type": "GROUP",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "intensity": "MEDIUM",
                        "location": "string",
                        "notes": "string",
                    }
                ],
            },
            {"option_id": "option_2"},
            {"option_id": "option_3"},
        ]
    }


def _as_positive_int(value, *, field):
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise AIPlanInvalidResponse(f"{field} must be an integer.") from exc
    if integer <= 0:
        raise AIPlanInvalidResponse(f"{field} must be positive.")
    return integer


def _required_text(mapping, key):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    value = str(value or "").strip()
    if not value:
        raise AIPlanInvalidResponse(f"Missing required field: {key}.")
    return value


def _text_or_default(value, default):
    value = str(value or "").strip()
    return value or default
