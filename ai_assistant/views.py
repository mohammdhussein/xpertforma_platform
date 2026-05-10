from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.queries.user_info import get_primary_role, get_user_roles
from accounts.statuses import is_approved_coach_approval_status
from ai_assistant.serializers import AIChatRequestSerializer
from ai_assistant.services.ai_attention_response import stabilize_attention_response
from ai_assistant.services.ai_chat_history import (
    conversation_scope_text,
    format_chat_history_for_prompt,
    get_cached_chat_history,
    remember_chat_turn,
    should_route_with_history,
)
from ai_assistant.services.backend_scope_guard import BACKEND_BLOCKED_RESPONSE, is_backend_data_question
from ai_assistant.services.context_builder import build_backend_context
from ai_assistant.services.data_router import route_backend_data_question
from ai_assistant.services.ai_fast_answers import build_fast_backend_response, looks_like_echo_answer
from ai_assistant.services.gemini_client import GeminiClient, GeminiServiceUnavailable
from ai_assistant.services.ollama_client import OllamaClient, OllamaServiceUnavailable
from ai_assistant.services.prompt_builder import build_backend_data_prompts
from ai_assistant.services.response_parser import parse_ai_response


class AIChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not settings.AI_ASSISTANT_ENABLED:
            return Response(
                {"detail": "AI assistant is disabled"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        history = data.get("history") or get_cached_chat_history(request.user)
        route_with_history = should_route_with_history(data["message"], history)
        routing_message = conversation_scope_text(data["message"], history) if route_with_history else data["message"]

        if not is_backend_data_question(routing_message, data.get("screen")):
            return Response(BACKEND_BLOCKED_RESPONSE)

        role = _resolve_ai_role(request.user)
        route = route_backend_data_question(routing_message, data.get("screen"))
        if not route.get("is_backend_related"):
            return Response(BACKEND_BLOCKED_RESPONSE)

        try:
            context_data = build_backend_context(
                user=request.user,
                route=route,
                screen=data["screen"],
                selected_player_id=data.get("selected_player_id"),
            )
            fast_response = build_fast_backend_response(
                context_data=context_data,
                route=route,
                user_message=data["message"],
            )
            if fast_response is not None:
                remember_chat_turn(
                    request.user,
                    history,
                    user_message=data["message"],
                    assistant_answer=fast_response.get("answer", ""),
                )
                return Response(fast_response)

            system_prompt, user_prompt = build_backend_data_prompts(
                user_role=role,
                screen=data["screen"],
                route=route,
                context_data=context_data,
                user_message=data["message"],
                conversation_history=format_chat_history_for_prompt(history),
            )
            raw_answer = _get_ai_client().chat(system_prompt, user_prompt)
        except (GeminiServiceUnavailable, OllamaServiceUnavailable):
            return Response(
                {"detail": "AI service is unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_data = stabilize_attention_response(
            parse_ai_response(raw_answer),
            context_data=context_data,
            route=route,
            user_message=data["message"],
        )
        fallback_response = build_fast_backend_response(
            context_data=context_data,
            route=route,
            user_message=data["message"],
        )
        if fallback_response is not None and looks_like_echo_answer(response_data, data["message"]):
            response_data = fallback_response

        remember_chat_turn(
            request.user,
            history,
            user_message=data["message"],
            assistant_answer=response_data.get("answer", ""),
        )
        return Response(response_data)


def _get_ai_client():
    provider = getattr(settings, "AI_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return OllamaClient()
    if provider == "gemini":
        return GeminiClient()
    raise OllamaServiceUnavailable("Unsupported AI provider")


def _resolve_ai_role(user):
    if user.is_staff or user.is_superuser:
        return "ADMIN"

    roles = get_user_roles(user)
    primary_role = get_primary_role(roles)

    if primary_role == "Coach" and hasattr(user, "coach_profile"):
        _ensure_approved_coach(user)
        return "COACH"
    if primary_role == "Player" and hasattr(user, "player_profile"):
        return "PLAYER"
    if hasattr(user, "coach_profile"):
        _ensure_approved_coach(user)
        return "COACH"
    if hasattr(user, "player_profile"):
        return "PLAYER"

    raise PermissionDenied("AI assistant is available for players and coaches.")


def _ensure_approved_coach(user):
    if not is_approved_coach_approval_status(user.coach_profile.approval_status):
        raise PermissionDenied("Coach account is not approved.")
