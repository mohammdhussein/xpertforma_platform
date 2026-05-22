from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.statuses import is_approved_coach_approval_status
from ai_assistant.coach_ai_assistant_serializers import (
    AIActionConfirmRequestSerializer,
    AIChatRequestSerializer,
)
from ai_assistant.services.coach_ai_assistant_groq import (
    GroqConfigurationError,
    GroqServiceUnavailable,
    GroqTimeout,
)
from ai_assistant.services.coach_ai_assistant_html import (
    render_answer_html,
    render_plan_options_html,
)
from ai_assistant.services.coach_ai_assistant_players import (
    build_select_player_actions,
    format_player_names,
    resolve_coach_player_targets,
)
from ai_assistant.services.coach_ai_assistant_plans import (
    AIPlanDraftExpired,
    AIPlanDraftPermissionDenied,
    AIPlanInvalidResponse,
    AIPlanInvalidSelection,
    create_training_plan_from_draft_option,
    generate_plan_options_for_players,
    is_plan_suggestion_request,
    parse_requested_plan_date_range,
)
from ai_assistant.services.user_ai_assistant_chat import generate_chatbot_answer
from training.serializers.training_plans import TrainingPlanCreateResultSerializer


class AIChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data["message"]

        disabled_response = _disabled_or_missing_key_response()
        if disabled_response is not None:
            return disabled_response

        if not is_plan_suggestion_request(message):
            try:
                answer = generate_chatbot_answer(user=request.user, message=message)
            except GroqConfigurationError:
                return Response(
                    {"detail": "Missing GROQ_API_KEY."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            except GroqTimeout:
                return Response(
                    {"detail": "Groq request timed out."},
                    status=status.HTTP_504_GATEWAY_TIMEOUT,
                )
            except GroqServiceUnavailable as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                _mobile_response(
                    answer=answer,
                    html=render_answer_html(answer),
                    suggested_questions=_suggested_questions(request.user, mode="chat"),
                )
            )

        _ensure_approved_coach(request.user)
        player_resolution = resolve_coach_player_targets(coach_user=request.user, message=message)
        if player_resolution["status"] == "no_match":
            name_hint = player_resolution.get("name_hint")
            answer = (
                f"I could not find {name_hint} in your roster. Please include the player's full name."
                if name_hint
                else "I could not find that player in your roster. Please include the player's full name."
            )
            return Response(
                _mobile_response(
                    answer=answer,
                    html=render_answer_html(answer),
                    suggested_questions=_suggested_questions(request.user, mode="no_player"),
                )
            )
        if player_resolution["status"] == "ambiguous":
            name_hint = player_resolution.get("name_hint")
            answer = (
                f"I found more than one match for {name_hint}. Please choose the player before I draft plans."
                if name_hint
                else "I found more than one matching player. Please choose the player before I draft plans."
            )
            return Response(
                _mobile_response(
                    answer=answer,
                    html=render_answer_html(answer),
                    actions=build_select_player_actions(player_resolution["profiles"]),
                    suggested_questions=_suggested_questions(request.user, mode="multiple_players"),
                )
            )

        try:
            player_profiles = player_resolution["profiles"]
            requested_date_range = parse_requested_plan_date_range(message)
            draft, options = generate_plan_options_for_players(
                coach_user=request.user,
                player_profiles=player_profiles,
                requested_date_range=requested_date_range,
            )
        except GroqConfigurationError:
            return Response(
                {"detail": "Missing GROQ_API_KEY."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except GroqTimeout:
            return Response(
                {"detail": "Groq request timed out."},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except GroqServiceUnavailable as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except AIPlanInvalidResponse as exc:
            return Response(
                {"detail": "Groq returned an invalid plan response.", "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        player_name = format_player_names(player_profiles)
        answer = f"I drafted 3 training plan options for {player_name}."
        actions = [
            {
                "type": "select_plan_option",
                "label": f"Use {option['title']}",
                "draft_id": str(draft.draft_id),
                "option_id": option["option_id"],
                "requires_confirmation": True,
            }
            for option in options
        ]
        return Response(
            _mobile_response(
                answer=answer,
                html=render_plan_options_html(player_name=player_name, options=options),
                actions=actions,
                suggested_questions=_suggested_questions(request.user, mode="plan", player_name=player_name),
            )
        )


class AIActionConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIActionConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not getattr(settings, "AI_ASSISTANT_ENABLED", False):
            return Response(
                {"detail": "AI assistant is disabled"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        _ensure_approved_coach(request.user)
        try:
            result = create_training_plan_from_draft_option(
                coach_user=request.user,
                draft_id=data["draft_id"],
                selected_option_id=data["selected_option_id"],
            )
        except AIPlanDraftExpired:
            return Response({"detail": "Draft has expired."}, status=status.HTTP_400_BAD_REQUEST)
        except AIPlanDraftPermissionDenied:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        except AIPlanInvalidSelection:
            return Response({"detail": "Invalid selected option."}, status=status.HTTP_400_BAD_REQUEST)
        except AIPlanInvalidResponse as exc:
            return Response(
                {"detail": "Validation failed.", "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": "success",
                **TrainingPlanCreateResultSerializer(result).data,
            },
            status=status.HTTP_201_CREATED,
        )


def _mobile_response(*, answer, html, actions=None, suggested_questions=None):
    return {
        "answer": answer,
        "render_type": "html",
        "html": html,
        "cards": [],
        "actions": actions or [],
        "suggested_questions": (suggested_questions or _default_suggested_questions())[:3],
    }


def _suggested_questions(user, *, mode, player_name=None):
    if mode == "plan" and player_name:
        return [
            f"Suggest 3 recovery plans for {player_name}",
            f"Suggest 3 speed plans for {player_name}",
            "How should I choose between these plans?",
        ]

    if mode == "no_player":
        return [
            "Suggest 3 plans using the player's full name",
            "What can you help me do as a coach?",
            "How should I structure this week's training?",
        ]

    if mode == "multiple_players":
        return [
            "Suggest 3 plans using the full player name",
            "What details can help identify the player?",
            "How should I choose a plan focus?",
        ]

    if hasattr(user, "player_profile"):
        return [
            "What should I focus on today?",
            "How should I recover after training?",
            "What should I ask my coach about my progress?",
        ]

    if hasattr(user, "coach_profile"):
        return [
            "Suggest 3 training plans for one of my players",
            "How should I structure this week's training?",
            "What can you help me do as a coach?",
        ]

    return _default_suggested_questions()


def _default_suggested_questions():
    return [
        "What can you help me with?",
        "How should I plan training this week?",
        "How can I improve recovery?",
    ]


def _disabled_or_missing_key_response():
    if not getattr(settings, "AI_ASSISTANT_ENABLED", False):
        return Response(
            {"detail": "AI assistant is disabled"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not getattr(settings, "GROQ_API_KEY", ""):
        return Response(
            {"detail": "Missing GROQ_API_KEY."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return None


def _ensure_approved_coach(user):
    if not hasattr(user, "coach_profile"):
        raise PermissionDenied("AI assistant plan actions are available for coaches.")
    if not is_approved_coach_approval_status(user.coach_profile.approval_status):
        raise PermissionDenied("Coach account is not approved.")
