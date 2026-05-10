from unittest.mock import Mock, patch
from datetime import datetime, time, timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from ai_assistant.services.backend_scope_guard import BACKEND_BLOCKED_RESPONSE, is_backend_data_question
from ai_assistant.services.context_builder import build_backend_context
from ai_assistant.services.data_catalog import DATA_ATTENDANCE, DATA_PLAYERS, DATA_SESSIONS
from ai_assistant.services.data_router import route_backend_data_question
from ai_assistant.services.ollama_client import OllamaClient
from ai_assistant.services.response_parser import parse_ai_response
from training.models import SessionAttendance, TrainingPlan, TrainingPlanPlayer, TrainingSession


CHAT_URL = "/api/ai/chat/"


def make_user_with_role(*, email, name, role_name, password="StrongPass123!"):
    role, _ = Role.objects.get_or_create(role_name=role_name)
    user = User.objects.create_user(email=email, password=password, name=name)
    UserRole.objects.create(user=user, role=role)
    return user


def make_ai_response(answer="ok"):
    return (
        '{"answer":"%s","cards":[],"actions":[],"suggested_questions":[]}'
        % answer
    )


class AIChatViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.position = Position.objects.get(code="ST")

        self.player = make_user_with_role(
            email="ai-player@example.com",
            name="AI Player",
            role_name="Player",
        )
        PlayerProfile.objects.create(
            user=self.player,
            position=self.position,
            login_status="COMPLETE",
        )

        self.coach = make_user_with_role(
            email="ai-coach@example.com",
            name="AI Coach",
            role_name="Coach",
        )
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")

        self.other_coach = make_user_with_role(
            email="other-ai-coach@example.com",
            name="Other AI Coach",
            role_name="Coach",
        )
        CoachProfile.objects.create(user=self.other_coach, approval_status="APPROVED")

        self.other_player = make_user_with_role(
            email="other-ai-player@example.com",
            name="Other AI Player",
            role_name="Player",
        )
        PlayerProfile.objects.create(
            user=self.other_player,
            coach=self.other_coach,
            position=self.position,
            login_status="COMPLETE",
        )

    def test_auth_required(self):
        response = self.client.post(CHAT_URL, {"message": "What is my latest session?"}, format="json")

        self.assertEqual(response.status_code, 401)

    def test_missing_message_returns_400(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.post(CHAT_URL, {"screen": "PLAYER_PROGRESS"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.data)

    @override_settings(AI_ASSISTANT_ENABLED=False)
    @patch("ai_assistant.views.OllamaClient")
    def test_ai_disabled_returns_503(self, mock_ollama):
        self.client.force_authenticate(user=self.player)

        response = self.client.post(CHAT_URL, {"message": "What is my latest session?"}, format="json")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"detail": "AI assistant is disabled"})
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_general_question_blocked_and_ai_not_called(self, mock_ollama):
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "Tell me a joke", "screen": "PLAYER_HOME"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, BACKEND_BLOCKED_RESPONSE)
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_backend_data_question_allowed_and_calls_ollama(self, mock_ollama):
        ai_client = Mock()
        ai_client.chat.return_value = make_ai_response("Your focus is available.")
        mock_ollama.return_value = ai_client
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "What should I focus on today?", "screen": "PLAYER_PROGRESS"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["answer"], "Your focus is available.")
        mock_ollama.assert_called_once()
        ai_client.chat.assert_called_once()
        user_prompt = ai_client.chat.call_args.args[1]
        self.assertIn("CONTEXT_DATA:", user_prompt)
        self.assertIn('"performance"', user_prompt)

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_today_session_question_uses_fast_backend_answer(self, mock_ollama):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Fast Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        TrainingSession.objects.create(
            plan=plan,
            title="Fast Session",
            session_date=today,
            start_time="08:00",
            end_time="09:00",
        )
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "What was my session today?", "screen": "PLAYER_HOME"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Fast Session", response.data["answer"])
        self.assertIn(str(today), response.data["answer"])
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_today_session_question_returns_clear_empty_fast_answer(self, mock_ollama):
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "What was my session today?", "screen": "PLAYER_HOME"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["answer"], "No sessions are scheduled for today.")
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_weekly_progress_question_uses_progress_not_attendance_history(self, mock_ollama):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Weekly Progress Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        completed = TrainingSession.objects.create(plan=plan, title="Completed Today", session_date=today)
        TrainingSession.objects.create(plan=plan, title="Planned Today", session_date=today)
        SessionAttendance.objects.create(
            session=completed,
            player=self.player,
            status=SessionAttendance.PRESENT,
            marked_by=self.coach,
        )
        self.client.force_authenticate(user=self.player)

        first_response = self.client.post(
            CHAT_URL,
            {"message": "What was my session today?", "screen": "PLAYER_HOME"},
            format="json",
        )
        second_response = self.client.post(
            CHAT_URL,
            {"message": "How is my weekly progress?"},
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertIn("Weekly progress", second_response.data["answer"])
        self.assertNotIn("Attendance summary", second_response.data["answer"])
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_attendance_question_still_uses_attendance_fast_answer(self, mock_ollama):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Attendance Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        attended = TrainingSession.objects.create(plan=plan, title="Attended", session_date=today)
        TrainingSession.objects.create(plan=plan, title="Missed", session_date=today)
        SessionAttendance.objects.create(
            session=attended,
            player=self.player,
            status=SessionAttendance.PRESENT,
            marked_by=self.coach,
        )
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "Show my attendance summary", "screen": "PLAYER_PROGRESS"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Attendance summary", response.data["answer"])
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="gemini", GEMINI_API_KEY=None)
    def test_missing_gemini_key_returns_503(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "What should I focus on today?", "screen": "PLAYER_PROGRESS"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"detail": "AI service is unavailable"})

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="unknown")
    @patch("ai_assistant.views.OllamaClient")
    @patch("ai_assistant.views.GeminiClient")
    def test_unsupported_provider_returns_503(self, mock_gemini, mock_ollama):
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "What should I focus on today?", "screen": "PLAYER_PROGRESS"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"detail": "AI service is unavailable"})
        mock_gemini.assert_not_called()
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_player_selected_player_id_is_ignored(self, mock_ollama):
        ai_client = Mock()
        ai_client.chat.return_value = make_ai_response("Only your data is shown.")
        mock_ollama.return_value = ai_client
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {
                "message": "Tell me about my profile",
                "screen": "PLAYER_PROGRESS",
                "selected_player_id": str(self.other_player.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI Player", response.data["answer"])
        self.assertNotIn("Other AI Player", str(response.data))
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_coach_cannot_access_unauthorized_selected_player(self, mock_ollama):
        self.client.force_authenticate(user=self.coach)

        response = self.client.post(
            CHAT_URL,
            {
                "message": "What is this player's attendance this month?",
                "screen": "COACH_PLAYER_PROFILE",
                "selected_player_id": str(self.other_player.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_follow_up_question_uses_cached_history(self, mock_ollama):
        ai_client = Mock()
        ai_client.chat.side_effect = [
            make_ai_response("Omar needs attention because he missed the latest session."),
            make_ai_response("Because Omar missed the latest session."),
        ]
        mock_ollama.return_value = ai_client
        self.client.force_authenticate(user=self.coach)

        first_response = self.client.post(
            CHAT_URL,
            {"message": "Why does Omar need attention?", "screen": "COACH_DASHBOARD"},
            format="json",
        )
        second_response = self.client.post(CHAT_URL, {"message": "why?"}, format="json")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertIn("missed the latest session", second_response.data["answer"])
        self.assertLessEqual(ai_client.chat.call_count, 2)

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_follow_up_question_uses_request_history(self, mock_ollama):
        ai_client = Mock()
        ai_client.chat.return_value = make_ai_response("Because Omar has a low attendance signal.")
        mock_ollama.return_value = ai_client
        self.client.force_authenticate(user=self.coach)

        response = self.client.post(
            CHAT_URL,
            {
                "message": "why?",
                "history": [
                    {"role": "user", "content": "Why does Omar need attention?"},
                    {"role": "assistant", "content": "Omar needs attention."},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["answer"], "Because Omar has a low attendance signal.")
        user_prompt = ai_client.chat.call_args.args[1]
        self.assertIn("RECENT_CONVERSATION:", user_prompt)
        self.assertIn("Why does Omar need attention?", user_prompt)

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_history_does_not_allow_general_blocked_question(self, mock_ollama):
        self.client.force_authenticate(user=self.coach)

        response = self.client.post(
            CHAT_URL,
            {
                "message": "What is the capital of France?",
                "history": [
                    {"role": "user", "content": "Why does Omar need attention?"},
                    {"role": "assistant", "content": "Omar needs attention."},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, BACKEND_BLOCKED_RESPONSE)
        mock_ollama.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_named_attention_question_expands_weak_yes_answer(self, mock_ollama):
        kareem = make_user_with_role(
            email="kareem-ai-player@example.com",
            name="Kareeem Abo Salah",
            role_name="Player",
        )
        PlayerProfile.objects.create(
            user=kareem,
            coach=self.coach,
            position=self.position,
            state=PlayerProfile.STATE_INJURED,
        )
        ai_client = Mock()
        ai_client.chat.return_value = make_ai_response("Yes")
        mock_ollama.return_value = ai_client
        self.client.force_authenticate(user=self.coach)

        response = self.client.post(
            CHAT_URL,
            {
                "message": "dose kareeem Abo salah needs attention?",
                "screen": "COACH_DASHBOARD",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Kareeem Abo Salah needs attention because", response.data["answer"])
        self.assertIn("injured", response.data["answer"])
        self.assertEqual(response.data["cards"][0]["severity"], "CRITICAL")

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_pronoun_attention_follow_up_expands_weak_yes_answer(self, mock_ollama):
        kareem = make_user_with_role(
            email="kareem-follow-up@example.com",
            name="Kareeem Abo Salah",
            role_name="Player",
        )
        PlayerProfile.objects.create(
            user=kareem,
            coach=self.coach,
            position=self.position,
            state=PlayerProfile.STATE_INJURED,
        )
        ai_client = Mock()
        ai_client.chat.side_effect = [
            make_ai_response("Yes"),
            make_ai_response("Yes"),
        ]
        mock_ollama.return_value = ai_client
        self.client.force_authenticate(user=self.coach)

        first_response = self.client.post(
            CHAT_URL,
            {"message": "dose kareeem Abo salah needs attention?"},
            format="json",
        )
        second_response = self.client.post(
            CHAT_URL,
            {"message": "why he need attention?"},
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertIn("Kareeem Abo Salah needs attention because", second_response.data["answer"])
        self.assertIn("injured", second_response.data["answer"])

    @override_settings(AI_ASSISTANT_ENABLED=True, AI_PROVIDER="ollama")
    @patch("ai_assistant.views.OllamaClient")
    def test_staff_named_attention_question_can_match_player_by_name(self, mock_ollama):
        self.coach.is_staff = True
        self.coach.save(update_fields=["is_staff"])
        kareem = make_user_with_role(
            email="kareem-staff-ai@example.com",
            name="Kareeem Abo Salah",
            role_name="Player",
        )
        PlayerProfile.objects.create(
            user=kareem,
            coach=self.coach,
            position=self.position,
            state=PlayerProfile.STATE_INJURED,
        )
        ai_client = Mock()
        ai_client.chat.return_value = make_ai_response("Yes")
        mock_ollama.return_value = ai_client
        self.client.force_authenticate(user=self.coach)

        response = self.client.post(
            CHAT_URL,
            {"message": "dose kareeem Abo salah needs attention?"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Kareeem Abo Salah needs attention because", response.data["answer"])
        self.assertIn("injured", response.data["answer"])


class BackendContextTests(TestCase):
    def setUp(self):
        self.position = Position.objects.get(code="ST")
        self.player = make_user_with_role(
            email="context-player@example.com",
            name="Context Player",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=self.player, position=self.position)
        self.coach = make_user_with_role(
            email="context-coach@example.com",
            name="Context Coach",
            role_name="Coach",
        )
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")
        self.coach_player = make_user_with_role(
            email="context-coach-player@example.com",
            name="Coach Player",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=self.coach_player, coach=self.coach, position=self.position)

    def test_latest_session_route_fetches_one_latest_session_only(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Player Plan",
            start_date=yesterday,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        TrainingSession.objects.create(plan=plan, title="Old Session", session_date=yesterday)
        TrainingSession.objects.create(plan=plan, title="Latest Session", session_date=today)
        route = {
            "is_backend_related": True,
            "data_sources": [DATA_SESSIONS],
            "time_range": {"type": "latest"},
            "target": {"type": "self", "selected_player_id_required": False},
            "question_type": "latest",
        }

        context = build_backend_context(self.player, route, "PLAYER_HOME")

        self.assertEqual(context["sessions"]["latest"]["title"], "Latest Session")
        self.assertNotIn("recent", context["sessions"])
        self.assertNotIn("upcoming", context["sessions"])

    def test_weekly_completed_sessions_are_calculated_by_backend(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Weekly Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        completed = TrainingSession.objects.create(plan=plan, title="Completed", session_date=today)
        TrainingSession.objects.create(plan=plan, title="Missed", session_date=today)
        SessionAttendance.objects.create(
            session=completed,
            player=self.player,
            status=SessionAttendance.PRESENT,
            marked_by=self.coach,
        )
        route = {
            "is_backend_related": True,
            "data_sources": [DATA_SESSIONS, DATA_ATTENDANCE],
            "time_range": {"type": "week", "days": 7},
            "target": {"type": "self", "selected_player_id_required": False},
            "question_type": "count",
        }

        context = build_backend_context(self.player, route, "PLAYER_PROGRESS")

        self.assertEqual(context["sessions"]["counts"]["planned"], 2)
        self.assertEqual(context["sessions"]["counts"]["completed"], 1)
        self.assertEqual(context["sessions"]["counts"]["missed"], 1)
        self.assertEqual(context["attendance"]["summary"]["attendance_rate"], 50)

    def test_today_past_session_is_not_upcoming(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Today Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        TrainingSession.objects.create(
            plan=plan,
            title="Past Today",
            session_date=today,
            start_time="08:00",
        )
        route = {
            "is_backend_related": True,
            "data_sources": [DATA_SESSIONS],
            "time_range": {"type": "default"},
            "target": {"type": "self", "selected_player_id_required": False},
            "question_type": "summary",
        }

        fixed_now = timezone.make_aware(datetime.combine(today, time(hour=12)))
        with (
            patch("ai_assistant.services.context_builder.timezone.now", return_value=fixed_now),
            patch("ai_assistant.services.context_builder.timezone.localtime", side_effect=lambda value, *args, **kwargs: value),
        ):
            context = build_backend_context(self.player, route, "PLAYER_HOME")

        self.assertEqual(context["sessions"]["upcoming"], [])

    def test_coach_selected_player_attendance_is_compact_and_permission_safe(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Coach Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.coach_player, assigned_by=self.coach)
        session = TrainingSession.objects.create(plan=plan, title="Coach Session", session_date=today)
        SessionAttendance.objects.create(
            session=session,
            player=self.coach_player,
            status=SessionAttendance.PRESENT,
            marked_by=self.coach,
        )
        route = {
            "is_backend_related": True,
            "data_sources": [DATA_ATTENDANCE, DATA_PLAYERS],
            "time_range": {"type": "month", "days": 30},
            "target": {"type": "selected_player", "selected_player_id_required": True},
            "question_type": "summary",
        }

        context = build_backend_context(
            self.coach,
            route,
            "COACH_PLAYER_PROFILE",
            selected_player_id=self.coach_player.id,
        )

        self.assertEqual(context["attendance"]["summary"]["planned"], 1)
        self.assertEqual(context["attendance"]["summary"]["attended"], 1)
        self.assertEqual(context["players"]["selected_player"]["name"], "Coach Player")
        self.assertNotIn("Other AI Player", str(context))


class DataRouterAndScopeTests(TestCase):
    def test_backend_scope_allows_backend_data_and_blocks_general(self):
        self.assertTrue(is_backend_data_question("How many sessions did I complete this week?", "PLAYER_PROGRESS"))
        self.assertTrue(is_backend_data_question("What is Omar's attendance this month?", "COACH_PLAYER_PROFILE"))
        self.assertTrue(is_backend_data_question("but the day is 5/6 now its upcoming?"))
        self.assertFalse(is_backend_data_question("What is the capital of France?", "PLAYER_HOME"))
        self.assertFalse(is_backend_data_question("Write Python code", "COACH_DASHBOARD"))

    def test_router_detects_sessions_attendance_weekly_count(self):
        route = route_backend_data_question("How many sessions did I complete this week?", "PLAYER_PROGRESS")

        self.assertTrue(route["is_backend_related"])
        self.assertEqual(route["time_range"]["type"], "week")
        self.assertEqual(route["target"]["type"], "self")
        self.assertEqual(route["question_type"], "count")
        self.assertIn(DATA_SESSIONS, route["data_sources"])
        self.assertIn(DATA_ATTENDANCE, route["data_sources"])

    def test_router_detects_named_player_without_possessive(self):
        route = route_backend_data_question("Why does Omar need attention?", None)

        self.assertTrue(route["is_backend_related"])
        self.assertEqual(route["target"]["type"], "selected_player")
        self.assertEqual(route["target"]["name_hint"], "omar")

    def test_router_detects_named_player_with_misspelled_does_on_dashboard(self):
        route = route_backend_data_question("dose kareeem Abo salah needs attention?", "COACH_DASHBOARD")

        self.assertTrue(route["is_backend_related"])
        self.assertEqual(route["target"]["type"], "selected_player")
        self.assertEqual(route["target"]["name_hint"], "kareeem abo salah")


class AIResponseParserTests(TestCase):
    def test_invalid_gemini_json_still_returns_mobile_shape(self):
        response = parse_ai_response("Plain answer from Gemini")

        self.assertEqual(response["answer"], "Plain answer from Gemini")
        self.assertEqual(response["cards"], [])
        self.assertEqual(response["actions"], [])
        self.assertEqual(len(response["suggested_questions"]), 3)

    def test_cards_actions_and_suggestions_are_limited_and_normalized(self):
        raw = (
            '{"answer":"ok","cards":['
            '{"title":"a","value":"1","severity":"BAD"},'
            '{"title":"b","value":"2","severity":"WARNING"},'
            '{"title":"c","value":"3","severity":"CRITICAL"},'
            '{"title":"d","value":"4","severity":"INFO"}'
            '],"actions":[{"label":"x","type":"x","payload":{}},{"label":"y","type":"y","payload":{}},'
            '{"label":"z","type":"z","payload":{}},{"label":"w","type":"w","payload":{}}],'
            '"suggested_questions":["1","2","3","4"]}'
        )

        response = parse_ai_response(raw)

        self.assertEqual(len(response["cards"]), 3)
        self.assertEqual(response["cards"][0]["severity"], "INFO")
        self.assertEqual(len(response["actions"]), 3)
        self.assertEqual(response["suggested_questions"], ["1", "2", "3"])


class OllamaClientTests(TestCase):
    @override_settings(
        AI_RESPONSE_TEMPERATURE=0,
        AI_RANDOM_SEED=42,
        OLLAMA_NUM_PREDICT=123,
        OLLAMA_CHAT_MODEL="qwen3:4b",
        OLLAMA_FALLBACK_MODEL="llama3.2:3b",
    )
    @patch("ai_assistant.services.ollama_client.requests.post")
    def test_chat_uses_deterministic_options(self, mock_post):
        response = Mock()
        response.json.return_value = {"message": {"content": "{}"}}
        response.raise_for_status.return_value = None
        mock_post.return_value = response

        OllamaClient().chat("system", "user")

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual(payload["options"]["seed"], 42)
        self.assertEqual(payload["options"]["num_predict"], 123)
