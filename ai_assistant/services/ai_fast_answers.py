import re

from ai_assistant.services.ai_attention_response import build_selected_player_attention_response
from ai_assistant.services.data_catalog import (
    DATA_ATTENDANCE,
    DATA_CHECKINS,
    DATA_PERFORMANCE,
    DATA_PLAYERS,
    DATA_PROFILE,
    DATA_SESSIONS,
)
from ai_assistant.services.response_parser import DEFAULT_SUGGESTED_QUESTIONS


def build_fast_backend_response(*, context_data, route, user_message):
    response = _build_attention_response(context_data, route, user_message)
    if response is not None:
        return response

    response = _build_profile_response(context_data, user_message)
    if response is not None:
        return response

    response = _build_session_response(context_data, route, user_message)
    if response is not None:
        return response

    response = _build_progress_response(context_data, route, user_message)
    if response is not None:
        return response

    response = _build_attendance_response(context_data, route, user_message)
    if response is not None:
        return response

    response = _build_checkin_response(context_data, route, user_message)
    if response is not None:
        return response

    return None


def _build_profile_response(context_data, user_message):
    if not _has_any_token(user_message, {"account", "height", "profile", "position", "status", "state", "weight"}):
        return None

    profile_payload = context_data.get(DATA_PROFILE) or {}
    profile = profile_payload.get("self") or profile_payload.get("selected_player") or profile_payload.get("coach") or profile_payload.get("admin")
    if not isinstance(profile, dict):
        return None

    name = _display(profile.get("name"))
    position = _position_name(profile.get("position"))
    state = profile.get("state")
    height = profile.get("height_cm")
    weight = profile.get("weight_kg")
    foot = profile.get("foot")
    answer_parts = [f"Profile for {name}."]
    if position:
        answer_parts.append(f"Position: {position}.")
    if state:
        answer_parts.append(f"Status: {state}.")
    if height is not None:
        answer_parts.append(f"Height: {height} cm.")
    if weight is not None:
        answer_parts.append(f"Weight: {weight} kg.")
    if foot:
        answer_parts.append(f"Preferred foot: {foot}.")

    cards = [
        {"title": "Name", "value": name, "severity": "INFO"},
    ]
    if position:
        cards.append({"title": "Position", "value": position, "severity": "INFO"})
    if state:
        cards.append({"title": "Status", "value": str(state), "severity": "WARNING" if str(state).upper() == "INJURED" else "INFO"})

    return _response(
        " ".join(answer_parts),
        cards=cards[:3],
        suggested_questions=[
            "What is my latest session?",
            "Show my attendance summary",
            "How is my weekly progress?",
        ],
    )


def _build_attention_response(context_data, route, user_message):
    if not _has_any_token(user_message, {"attention", "risk", "alert", "alerts"}):
        return None

    selected_player = (context_data.get(DATA_PLAYERS) or {}).get("selected_player")
    if isinstance(selected_player, dict):
        return build_selected_player_attention_response(selected_player)

    players_payload = context_data.get(DATA_PLAYERS) or {}
    needs_attention = players_payload.get("needs_attention") or []
    if not isinstance(needs_attention, list):
        return None

    if not needs_attention:
        return _response(
            "No players need attention based on the provided data.",
            cards=[{"title": "Needs attention", "value": "0 players", "severity": "INFO"}],
            suggested_questions=[
                "Who has low attendance?",
                "Which players missed training?",
                "Show team readiness",
            ],
        )

    names = [str(player.get("name") or "").strip() for player in needs_attention if isinstance(player, dict)]
    names = [name for name in names if name]
    answer = f"{len(names)} player{'s' if len(names) != 1 else ''} need attention: {', '.join(names)}."
    cards = [
        {
            "title": player.get("name") or "Player",
            "value": _join_reasons(player.get("attention_reasons")) or "Needs attention",
            "severity": _severity_for_reasons(player.get("attention_reasons")),
        }
        for player in needs_attention[:3]
        if isinstance(player, dict)
    ]
    return _response(
        answer,
        cards=cards,
        suggested_questions=[
            f"Why does {names[0]} need attention?" if names else "Why do they need attention?",
            "Who missed the latest session?",
            "Show team readiness",
        ],
    )


def _build_session_response(context_data, route, user_message):
    if DATA_SESSIONS not in set(route.get("data_sources") or []):
        return None

    sessions_payload = context_data.get(DATA_SESSIONS) or {}
    if sessions_payload.get("missing"):
        return _response(str(sessions_payload.get("reason") or "No session data is available."))

    time_type = (route.get("time_range") or {}).get("type")
    question_type = route.get("question_type")
    if time_type == "today":
        today_sessions = _sessions_for_date_window(sessions_payload, context_data)
        if not today_sessions:
            return _response(
                "No sessions are scheduled for today.",
                cards=[{"title": "Today", "value": "No sessions", "severity": "INFO"}],
                suggested_questions=[
                    "What is my latest session?",
                    "What is my next session?",
                    "Show my attendance summary",
                ],
            )
        return _response(
            _session_list_sentence("Today", today_sessions),
            cards=[_session_card(session) for session in today_sessions[:3]],
            suggested_questions=[
                "What is my next session?",
                "Did I attend today's session?",
                "Show my attendance summary",
            ],
        )

    if question_type == "latest" or time_type == "latest" or _has_any_token(user_message, {"latest", "last"}):
        latest = sessions_payload.get("latest")
        if latest is None:
            return _response("No completed or past session was found in the provided data.")
        return _response(
            f"Your latest session was {_format_session(latest)}.",
            cards=[_session_card(latest)],
            suggested_questions=[
                "Did I attend it?",
                "What is my next session?",
                "Show my attendance summary",
            ],
        )

    if question_type == "count":
        counts = sessions_payload.get("counts") or {}
        planned = counts.get("planned", counts.get("sessions", 0))
        completed = counts.get("completed", counts.get("attended_player_sessions", counts.get("attended", 0)))
        missed = counts.get("missed", counts.get("missed_player_sessions", 0))
        return _response(
            f"You have {planned} planned session{'s' if planned != 1 else ''}, {completed} completed, and {missed} missed in this period.",
            cards=[
                {"title": "Planned", "value": str(planned), "severity": "INFO"},
                {"title": "Completed", "value": str(completed), "severity": "INFO"},
                {"title": "Missed", "value": str(missed), "severity": "WARNING" if missed else "INFO"},
            ],
        )

    return None


def _build_progress_response(context_data, route, user_message):
    if not _has_any_token(user_message, {"performance", "progress", "score", "effort", "consistency"}):
        return None
    if DATA_PERFORMANCE not in set(route.get("data_sources") or []):
        return None

    performance_payload = context_data.get(DATA_PERFORMANCE) or {}
    summary = performance_payload.get("summary")
    if isinstance(summary, dict):
        planned = summary.get("sessions_planned", 0)
        completed = summary.get("sessions_completed", 0)
        completion_rate = summary.get("completion_rate")
        average_score = summary.get("average_score")
        average_recovery = summary.get("average_recovery")
        readiness_checkins_logged = summary.get("readiness_checkins_logged", 0)
        score_text = f" Average score is {average_score}." if average_score is not None else ""
        recovery_text = (
            f" Average recovery is {average_recovery}%."
            if average_recovery is not None and readiness_checkins_logged
            else " No readiness check-ins are logged for this period, so recovery data is missing."
        )
        return _response(
            (
                f"Weekly progress: {completed} of {planned} sessions completed"
                f"{_percent_phrase(completion_rate)}.{score_text}{recovery_text}"
            ),
            cards=[
                {"title": "Completed", "value": f"{completed}/{planned}", "severity": "INFO"},
                {"title": "Completion", "value": f"{completion_rate}%" if completion_rate is not None else "N/A", "severity": _rate_severity(completion_rate)},
                {"title": "Average score", "value": _display(average_score), "severity": _score_severity(average_score)},
            ],
            suggested_questions=[
                "What sessions did I miss?",
                "What is my latest session?",
                "How can I improve recovery?",
            ],
        )

    latest_day = performance_payload.get("latest_day")
    if isinstance(latest_day, dict):
        sessions = latest_day.get("sessions") or {}
        score = latest_day.get("score")
        completed = sessions.get("completed", 0)
        planned = sessions.get("planned", 0)
        return _response(
            f"Latest progress day: {completed} of {planned} sessions completed, with score {_display(score)}.",
            cards=[
                {"title": "Completed", "value": f"{completed}/{planned}", "severity": "INFO"},
                {"title": "Score", "value": _display(score), "severity": _score_severity(score)},
            ],
        )

    return None


def _build_attendance_response(context_data, route, user_message):
    if not _has_any_token(user_message, {"attendance", "attended", "missed", "absent", "present", "late"}):
        return None
    if DATA_ATTENDANCE not in set(route.get("data_sources") or []):
        return None

    attendance_payload = context_data.get(DATA_ATTENDANCE) or {}
    summary = attendance_payload.get("summary") or (context_data.get(DATA_SESSIONS) or {}).get("counts")
    if not isinstance(summary, dict):
        return None

    planned = summary.get("planned", summary.get("expected_player_sessions", summary.get("sessions", 0)))
    attended = summary.get("attended", summary.get("attended_player_sessions", 0))
    missed = summary.get("missed", summary.get("missed_player_sessions", 0))
    rate = summary.get("attendance_rate")
    rate_text = f" Attendance rate is {rate}%." if rate is not None else ""
    return _response(
        f"Attendance summary: {attended} attended out of {planned} planned, with {missed} missed.{rate_text}",
        cards=[
            {"title": "Attended", "value": str(attended), "severity": "INFO"},
            {"title": "Missed", "value": str(missed), "severity": "WARNING" if missed else "INFO"},
            {"title": "Rate", "value": f"{rate}%" if rate is not None else "N/A", "severity": "INFO"},
        ],
        suggested_questions=[
            "Which sessions were missed?",
            "What is my latest session?",
            "How is my weekly progress?",
        ],
    )


def _build_checkin_response(context_data, route, user_message):
    if DATA_CHECKINS not in set(route.get("data_sources") or []):
        return None

    checkins_payload = context_data.get(DATA_CHECKINS) or {}
    latest = checkins_payload.get("latest")
    if isinstance(latest, dict):
        return _response(
            _checkin_sentence(latest),
            cards=[
                {"title": "Readiness", "value": _display(latest.get("readiness_score")), "severity": _readiness_severity(latest.get("readiness_score"))},
                {"title": "Sleep", "value": _display(latest.get("sleep_hours")), "severity": "INFO"},
                {"title": "Mood", "value": _display(latest.get("mood")), "severity": "INFO"},
            ],
            suggested_questions=[
                "How can I improve recovery?",
                "What should I focus on today?",
                "Show my latest session",
            ],
        )

    return None


def looks_like_echo_answer(response_data, user_message):
    answer = _normalize_answer(response_data.get("answer") if isinstance(response_data, dict) else "")
    question = _normalize_answer(user_message)
    return bool(answer and question and answer == question)


def _sessions_for_date_window(sessions_payload, context_data):
    date_window = (context_data.get("metadata") or {}).get("date_window") or {}
    start_date = str(date_window.get("start_date") or "")
    end_date = str(date_window.get("end_date") or "")
    candidates = []
    for session in sessions_payload.get("recent") or []:
        if not isinstance(session, dict):
            continue
        session_date = str(session.get("session_date") or "")
        if session_date and start_date <= session_date <= end_date:
            candidates.append(session)
    return candidates


def _session_list_sentence(prefix, sessions):
    if len(sessions) == 1:
        return f"{prefix}, your session is {_format_session(sessions[0])}."
    return f"{prefix}, you have {len(sessions)} sessions: " + "; ".join(_format_session(session) for session in sessions) + "."


def _format_session(session):
    title = str(session.get("title") or "Untitled session").strip()
    date = str(session.get("session_date") or "").strip()
    start = str(session.get("start_time") or "").strip()
    end = str(session.get("end_time") or "").strip()
    status = str(session.get("status") or "").strip()
    pieces = [title]
    if date:
        pieces.append(f"on {date}")
    if start and end:
        pieces.append(f"from {start} to {end}")
    elif start:
        pieces.append(f"at {start}")
    if status:
        pieces.append(f"({status})")
    return " ".join(pieces)


def _session_card(session):
    status = str(session.get("status") or "INFO").upper()
    severity = "WARNING" if "MISSED" in status else "INFO"
    return {
        "title": str(session.get("title") or "Session"),
        "value": _format_session(session),
        "severity": severity,
    }


def _checkin_sentence(checkin):
    date = checkin.get("date")
    readiness = checkin.get("readiness_score")
    sleep = checkin.get("sleep_hours")
    mood = checkin.get("mood")
    pieces = [f"Your latest check-in is from {date}." if date else "Your latest check-in is available."]
    if readiness is not None:
        pieces.append(f"Readiness is {readiness}.")
    if sleep is not None:
        pieces.append(f"Sleep was {sleep} hours.")
    if mood:
        pieces.append(f"Mood was {mood}.")
    return " ".join(pieces)


def _response(answer, *, cards=None, actions=None, suggested_questions=None):
    return {
        "answer": answer,
        "cards": cards or [],
        "actions": actions or [],
        "suggested_questions": (suggested_questions or DEFAULT_SUGGESTED_QUESTIONS)[:3],
    }


def _join_reasons(reasons):
    return ", ".join(str(reason).strip().rstrip(".") for reason in reasons or [] if str(reason).strip())


def _severity_for_reasons(reasons):
    text = _join_reasons(reasons).lower()
    if "injured" in text:
        return "CRITICAL"
    if "missed" in text or "low" in text:
        return "WARNING"
    return "INFO"


def _readiness_severity(value):
    try:
        score = int(value)
    except (TypeError, ValueError):
        return "INFO"
    if score < 40:
        return "CRITICAL"
    if score < 70:
        return "WARNING"
    return "INFO"


def _percent_phrase(value):
    if value is None:
        return ""
    return f" ({value}%)"


def _rate_severity(value):
    if value is None:
        return "INFO"
    if value < 50:
        return "CRITICAL"
    if value < 75:
        return "WARNING"
    return "INFO"


def _score_severity(value):
    if value is None:
        return "INFO"
    if value < 40:
        return "CRITICAL"
    if value < 70:
        return "WARNING"
    return "INFO"


def _has_any_token(value, tokens):
    return bool(set(re.findall(r"[a-z0-9]+", str(value or "").lower())) & tokens)


def _normalize_answer(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).rstrip("?.!")


def _display(value):
    if value is None or value == "":
        return "N/A"
    return str(value)


def _position_name(value):
    if isinstance(value, dict):
        return str(value.get("name") or value.get("code") or "").strip()
    return str(value or "").strip()
