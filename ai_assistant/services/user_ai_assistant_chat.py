import json
import re

from accounts.serializers.position import build_position_payload
from accounts.statuses import is_approved_coach_approval_status
from ai_assistant.services.coach_ai_assistant_groq import GroqChatClient
from ai_assistant.services.context_builder import build_backend_context
from ai_assistant.services.data_router import route_backend_data_question
from ai_assistant.services.ai_fast_answers import build_fast_backend_response
from ai_assistant.services.prompt_builder import build_backend_data_prompts
from ai_assistant.services.response_parser import parse_ai_response


def generate_chatbot_answer(*, user, message):
    backend_answer = generate_backend_data_answer(user=user, message=message)
    if backend_answer:
        return backend_answer

    system_prompt, user_prompt = build_chatbot_prompts(user=user, message=message)
    answer = GroqChatClient().chat_text(system_prompt=system_prompt, user_prompt=user_prompt)
    return (answer or "").strip() or "I could not generate an answer right now."


def generate_backend_data_answer(*, user, message):
    if not _has_app_data_keyword(message):
        return ""

    route = route_backend_data_question(message, None)
    if not route.get("is_backend_related"):
        return ""

    context_data = build_backend_context(
        user=user,
        route=route,
        screen="UNKNOWN",
        selected_player_id=None,
    )
    fast_response = build_fast_backend_response(
        context_data=context_data,
        route=route,
        user_message=message,
    )
    if fast_response is not None:
        return fast_response.get("answer", "")

    if not _should_use_groq_backend_answer(route):
        return ""

    system_prompt, user_prompt = build_backend_data_prompts(
        user_role=(context_data.get("metadata") or {}).get("user_role", "UNKNOWN"),
        screen="UNKNOWN",
        route=route,
        context_data=context_data,
        user_message=message,
    )
    raw_answer = GroqChatClient().chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
    return parse_ai_response(raw_answer).get("answer", "")


def _has_app_data_keyword(message):
    tokens = set(re.findall(r"[a-z0-9]+", str(message or "").lower()))
    return bool(
        tokens
        & {
            "alert",
            "alerts",
            "attendance",
            "checkin",
            "checkins",
            "coach",
            "coaches",
            "dashboard",
            "injured",
            "latest",
            "missed",
            "performance",
            "plan",
            "plans",
            "player",
            "players",
            "position",
            "positions",
            "progress",
            "readiness",
            "recovery",
            "roster",
            "schedule",
            "session",
            "sessions",
            "team",
            "teams",
            "training",
            "upcoming",
        }
    )


def _should_use_groq_backend_answer(route):
    sources = set(route.get("data_sources") or [])
    return bool(sources - {"profile"})


def build_chatbot_prompts(*, user, message):
    context = build_authenticated_user_context(user)
    system_prompt = (
        "You are the XpertForma AI assistant inside a football training app. "
        "You are both a friendly chatbot and an agent. "
        "For normal messages, answer conversationally and helpfully. "
        "For requests that require creating or changing backend records, explain that the app will show a native action "
        "when that action is supported. "
        "Do not invent player data, coach data, IDs, attendance, or plans that are not in the provided context. "
        "Do not ask the mobile app for selected_player_id, screen_context, user_id, coach_id, role, html, or player_id. "
        "Return plain text only. Do not return HTML, Markdown tables, JSON, JavaScript, or buttons."
    )
    user_prompt = json.dumps(
        {
            "authenticated_user_context": context,
            "message": message,
            "response_rules": [
                "Keep the answer concise and mobile friendly.",
                "If the user wants training plans for a named player, the backend agent route handles it separately.",
                "If information is missing, ask a short clarification question.",
            ],
        },
        ensure_ascii=True,
    )
    return system_prompt, user_prompt


def build_authenticated_user_context(user):
    role = "UNKNOWN"
    context = {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
    }

    if hasattr(user, "coach_profile"):
        role = "COACH"
        context["coach"] = {
            "approval_status": user.coach_profile.approval_status,
            "is_approved": is_approved_coach_approval_status(user.coach_profile.approval_status),
            "players": build_coach_roster_context(user),
        }
    elif hasattr(user, "player_profile"):
        role = "PLAYER"
        profile = user.player_profile
        context["player"] = {
            "position": build_position_payload(profile.position),
            "state": profile.state,
            "fitness_level": profile.fitness_level,
            "coach_name": profile.coach.name if profile.coach else "",
        }

    context["role"] = role
    return context


def build_coach_roster_context(coach_user):
    roster = []
    for profile in (
        coach_user.coached_players.select_related("user", "position")
        .order_by("user__first_name", "user__last_name", "user__email")[:25]
    ):
        roster.append(
            {
                "id": str(profile.user_id),
                "name": profile.user.name,
                "position": build_position_payload(profile.position),
                "state": profile.state,
            }
        )
    return roster
