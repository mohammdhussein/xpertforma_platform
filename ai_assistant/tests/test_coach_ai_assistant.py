import json
from datetime import time
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from openai import OpenAIError
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from ai_assistant.models import AIPlanDraft
from ai_assistant.services.coach_ai_assistant_groq import GroqChatClient, GroqServiceUnavailable, GroqTimeout
from ai_assistant.services.coach_ai_assistant_html import render_answer_html
from ai_assistant.services.coach_ai_assistant_plans import parse_plan_options
from training.models import SessionLifecycle, TrainingPlan, TrainingPlanPlayer, TrainingSession


CHAT_URL = "/api/ai/chat/"
CONFIRM_URL = "/api/ai/actions/confirm/"


def make_user_with_role(*, email, name, role_name, password="StrongPass123!"):
    role, _ = Role.objects.get_or_create(role_name=role_name)
    user = User.objects.create_user(email=email, password=password, name=name)
    UserRole.objects.create(user=user, role=role)
    return user


def make_plan_options_response():
    return json.dumps(
        {
            "options": [
                {
                    "option_id": "option_1",
                    "title": "Speed Plan",
                    "description": "Acceleration and repeat sprint quality.",
                    "duration": "7 days",
                    "difficulty": "Advanced",
                    "focus_areas": ["Acceleration", "Sprint mechanics"],
                    "sessions_count": 2,
                    "preview_sessions": [
                        {
                            "title": "Acceleration Mechanics",
                            "day_label": "Day 1",
                            "session_type": "INDIVIDUAL",
                            "start_time": "09:00",
                            "end_time": "10:00",
                            "intensity": "HIGH",
                            "location": "Main Field",
                            "notes": "Sprint mechanics and recovery spacing",
                        },
                        {
                            "title": "Repeat Sprint Blocks",
                            "day_label": "Day 3",
                            "session_type": "GROUP",
                            "start_time": "11:00",
                            "end_time": "12:00",
                            "intensity": "MEDIUM",
                            "location": "Pitch B",
                            "notes": "Short work-rest intervals",
                        },
                    ],
                },
                {
                    "option_id": "option_2",
                    "title": "Strength Plan",
                    "description": "Lower-body power and control.",
                    "duration": "7 days",
                    "difficulty": "Intermediate",
                    "focus_areas": ["Power", "Balance"],
                    "sessions_count": 1,
                    "preview_sessions": [
                        {
                            "title": "Power Circuit",
                            "day_label": "Day 2",
                            "session_type": "TEAM",
                            "start_time": "10:00",
                            "end_time": "11:15",
                            "intensity": "MEDIUM",
                            "location": "Gym",
                            "notes": "Controlled strength circuit",
                        }
                    ],
                },
                {
                    "option_id": "option_3",
                    "title": "Recovery Plan",
                    "description": "Load management with technical touches.",
                    "duration": "7 days",
                    "difficulty": "Light",
                    "focus_areas": ["Recovery", "Mobility"],
                    "sessions_count": 1,
                    "preview_sessions": [
                        {
                            "title": "Mobility Touches",
                            "day_label": "Day 1",
                            "session_type": "INDIVIDUAL",
                            "start_time": "08:30",
                            "end_time": "09:15",
                            "intensity": "LOW",
                            "location": "Recovery Area",
                            "notes": "Mobility and ball touches",
                        }
                    ],
                },
            ]
        }
    )


def make_one_option_response():
    payload = json.loads(make_plan_options_response())
    payload["options"] = payload["options"][:1]
    return json.dumps(payload)


def make_two_day_plan_options_response():
    return json.dumps(
        {
            "options": [
                {
                    "option_id": "option_1",
                    "title": "Two Day Speed Plan",
                    "description": "Short acceleration block for the requested players.",
                    "duration": "2 days",
                    "difficulty": "Advanced",
                    "focus_areas": ["Acceleration", "Ball speed"],
                    "sessions_count": 2,
                    "preview_sessions": [
                        {
                            "title": "Current Day Speed",
                            "day_label": "Day 1",
                            "session_type": "GROUP",
                            "start_time": "09:00",
                            "end_time": "10:00",
                            "intensity": "HIGH",
                            "location": "Main Field",
                            "notes": "Acceleration mechanics",
                        },
                        {
                            "title": "Tomorrow Finishing",
                            "day_label": "Day 2",
                            "session_type": "TEAM",
                            "start_time": "11:00",
                            "end_time": "12:00",
                            "intensity": "MEDIUM",
                            "location": "Pitch B",
                            "notes": "Finishing after sprints",
                        },
                    ],
                },
                {
                    "option_id": "option_2",
                    "title": "Two Day Strength Plan",
                    "description": "Power and control across two days.",
                    "duration": "2 days",
                    "difficulty": "Intermediate",
                    "focus_areas": ["Power", "Balance"],
                    "sessions_count": 1,
                    "preview_sessions": [
                        {
                            "title": "Power Circuit",
                            "day_label": "Day 1",
                            "session_type": "TEAM",
                            "start_time": "10:00",
                            "end_time": "11:00",
                            "intensity": "MEDIUM",
                            "location": "Gym",
                            "notes": "Controlled strength circuit",
                        }
                    ],
                },
                {
                    "option_id": "option_3",
                    "title": "Two Day Recovery Plan",
                    "description": "Recovery and mobility before the next session.",
                    "duration": "2 days",
                    "difficulty": "Light",
                    "focus_areas": ["Recovery", "Mobility"],
                    "sessions_count": 1,
                    "preview_sessions": [
                        {
                            "title": "Mobility Touches",
                            "day_label": "Day 2",
                            "session_type": "INDIVIDUAL",
                            "start_time": "08:30",
                            "end_time": "09:15",
                            "intensity": "LOW",
                            "location": "Recovery Area",
                            "notes": "Mobility and ball touches",
                        }
                    ],
                },
            ]
        }
    )


class CoachAIAssistantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.position = Position.objects.get(code="ST")
        self.coach = make_user_with_role(
            email="ai-coach@example.com",
            name="AI Coach",
            role_name="Coach",
        )
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")
        self.other_coach = make_user_with_role(
            email="other-ai-coach@example.com",
            name="Other Coach",
            role_name="Coach",
        )
        CoachProfile.objects.create(user=self.other_coach, approval_status="APPROVED")
        self.player = make_user_with_role(
            email="ahmad@example.com",
            name="Ahmad Saleh",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=self.player, coach=self.coach, position=self.position)
        self.other_coach_player = make_user_with_role(
            email="ahmad-other@example.com",
            name="Ahmad Other",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=self.other_coach_player, coach=self.other_coach, position=self.position)
        self.client.force_authenticate(user=self.coach)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_chat_accepts_message_and_response_format_only(self):
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            return_value=make_plan_options_response(),
        ):
            response = self.client.post(
                CHAT_URL,
                {"message": "Suggest 3 plans for Ahmad", "response_format": "html"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["render_type"], "html")
        self.assertEqual(response.data["cards"], [])
        self.assertEqual(len(response.data["suggested_questions"]), 3)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_non_plan_message_uses_chatbot_mode(self):
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_text",
            return_value="I can help with training, players, and plan creation.",
        ) as mock_chat:
            response = self.client.post(
                CHAT_URL,
                {"message": "What can you help me with?"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["answer"], "I can help with training, players, and plan creation.")
        self.assertEqual(response.data["render_type"], "html")
        self.assertEqual(response.data["actions"], [])
        self.assertEqual(len(response.data["suggested_questions"]), 3)
        mock_chat.assert_called_once()

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_player_can_use_chatbot_mode(self):
        self.client.force_authenticate(user=self.player)
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_text",
            return_value="Here is a simple recovery tip.",
        ):
            response = self.client.post(
                CHAT_URL,
                {"message": "hello assistant"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["answer"], "Here is a simple recovery tip.")
        self.assertEqual(response.data["actions"], [])
        self.assertEqual(len(response.data["suggested_questions"]), 3)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_latest_session_question_uses_backend_app_data(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Backend Data Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        TrainingSession.objects.create(
            plan=plan,
            title="Backend Latest Session",
            session_date=today,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )

        with patch("ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_text") as mock_chat:
            response = self.client.post(
                CHAT_URL,
                {"message": "what is the latest session?"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Backend Latest Session", response.data["answer"])
        self.assertEqual(response.data["actions"], [])
        self.assertEqual(len(response.data["suggested_questions"]), 3)
        mock_chat.assert_not_called()

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_latest_session_html_uses_completed_status_accent(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Completed Backend Plan",
            start_date=today,
            end_date=today,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        session = TrainingSession.objects.create(
            plan=plan,
            title="Backend Latest Session",
            session_date=today,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        SessionLifecycle.objects.create(session=session, status=SessionLifecycle.COMPLETED)

        with patch("ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_text") as mock_chat:
            response = self.client.post(
                CHAT_URL,
                {"message": "what is the latest session?"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Backend Latest Session", response.data["answer"])
        self.assertIn("border-left: 4px solid #22c55e", response.data["html"])
        self.assertIn("COMPLETED", response.data["html"])
        self.assertNotIn("box-shadow", response.data["html"])
        self.assertNotIn("border: 1px solid #dbe5f0", response.data["html"])
        self.assertEqual(response.data["actions"], [])
        self.assertEqual(len(response.data["suggested_questions"]), 3)
        mock_chat.assert_not_called()

    def test_answer_html_status_accent_colors(self):
        completed_html = render_answer_html("Your latest session was Speed (COMPLETED).")
        missed_html = render_answer_html("Your latest session was Speed (MISSED).")
        in_progress_html = render_answer_html("Your current session is Speed (IN_PROGRESS).")

        self.assertIn("border-left: 4px solid #22c55e", completed_html)
        self.assertIn("border-left: 4px solid #ef4444", missed_html)
        self.assertIn("border-left: 4px solid #1e6eeb", in_progress_html)
        self.assertNotIn("box-shadow", completed_html)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_selected_player_id_is_rejected(self):
        response = self.client.post(
            CHAT_URL,
            {
                "message": "Suggest 3 plans for Ahmad",
                "response_format": "html",
                "selected_player_id": str(self.other_coach_player.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("selected_player_id", response.data["unsupported_fields"])

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_screen_context_is_rejected(self):
        response = self.client.post(
            CHAT_URL,
            {
                "message": "Suggest 3 plans for Ahmad",
                "response_format": "html",
                "screen_context": "COACH_PLAYER_PROFILE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("screen_context", response.data["unsupported_fields"])

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_player_is_detected_from_message_inside_authenticated_coach_roster(self):
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            return_value=make_plan_options_response(),
        ):
            response = self.client.post(
                CHAT_URL,
                {"message": "Suggest 3 plans for Ahmad"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ahmad Saleh", response.data["answer"])
        self.assertNotIn("Ahmad Other", str(response.data))

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_multiple_same_name_players_return_select_player_actions(self):
        duplicate = make_user_with_role(
            email="ahmad-second@example.com",
            name="Ahmad Nasser",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=duplicate, coach=self.coach, position=self.position)

        response = self.client.post(
            CHAT_URL,
            {"message": "Suggest 3 plans for Ahmad"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual({action["type"] for action in response.data["actions"]}, {"select_player"})
        self.assertEqual(len(response.data["suggested_questions"]), 3)
        self.assertEqual(AIPlanDraft.objects.count(), 0)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_no_matching_player_asks_for_clarification(self):
        response = self.client.post(
            CHAT_URL,
            {"message": "Suggest 3 plans for Ziad"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("could not find", response.data["answer"].lower())
        self.assertEqual(response.data["actions"], [])
        self.assertEqual(len(response.data["suggested_questions"]), 3)
        self.assertEqual(AIPlanDraft.objects.count(), 0)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_plan_suggestion_returns_three_options_html_and_actions(self):
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            return_value=make_plan_options_response(),
        ):
            response = self.client.post(
                CHAT_URL,
                {"message": "Suggest 3 plans for Ahmad"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("html", response.data)
        self.assertIn("Speed Plan", response.data["html"])
        self.assertIn("#1e6eeb", response.data["html"])
        self.assertIn("#dbe5f0", response.data["html"])
        self.assertIn("#0f172a", response.data["html"])
        self.assertIn("Start date:", response.data["html"])
        self.assertIn("End date:", response.data["html"])
        self.assertIn("Start: 09:00", response.data["html"])
        self.assertIn("End: 10:00", response.data["html"])
        self.assertNotIn("<script", response.data["html"].lower())
        self.assertEqual(len(response.data["actions"]), 3)
        self.assertEqual(len(response.data["suggested_questions"]), 3)
        for action in response.data["actions"]:
            self.assertEqual(action["type"], "select_plan_option")
            self.assertTrue(action["draft_id"])
            self.assertTrue(action["option_id"].startswith("option_"))
            self.assertTrue(action["requires_confirmation"])

        draft = AIPlanDraft.objects.get()
        self.assertEqual(draft.coach, self.coach)
        self.assertEqual(draft.player, self.player)
        self.assertEqual({player.id for player in draft.target_players.all()}, {self.player.id})
        self.assertEqual(len(draft.options), 3)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_plan_suggestion_supports_multiple_players(self):
        omar = make_user_with_role(
            email="omar@example.com",
            name="Omar Fatoom",
            role_name="Player",
        )
        kareem = make_user_with_role(
            email="kareem@example.com",
            name="Kareem Abo Salah",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=omar, coach=self.coach, position=self.position)
        PlayerProfile.objects.create(user=kareem, coach=self.coach, position=self.position)

        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            return_value=make_plan_options_response(),
        ):
            response = self.client.post(
                CHAT_URL,
                {"message": "Suggest 3 training plans for omar and kareem"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Omar Fatoom and Kareem Abo Salah", response.data["answer"])
        self.assertEqual(len(response.data["actions"]), 3)
        draft = AIPlanDraft.objects.get()
        self.assertEqual(
            {player.id for player in draft.target_players.all()},
            {omar.id, kareem.id},
        )

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_plan_suggestion_supports_multiple_players_and_requested_date_range(self):
        omar = make_user_with_role(
            email="omar-date@example.com",
            name="Omar Fatoom",
            role_name="Player",
        )
        kareem = make_user_with_role(
            email="kareem-date@example.com",
            name="Kareem Abo Salah",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=omar, coach=self.coach, position=self.position)
        PlayerProfile.objects.create(user=kareem, coach=self.coach, position=self.position)

        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            return_value=make_two_day_plan_options_response(),
        ):
            response = self.client.post(
                CHAT_URL,
                {
                    "message": (
                        "Suggest 3 training plans for omar and kareem abo salah both "
                        "to start from the current day and to end in the tomorrow day?"
                    )
                },
                format="json",
            )

        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Omar Fatoom and Kareem Abo Salah", response.data["answer"])
        self.assertIn(f"Start date: {today.isoformat()}", response.data["html"])
        self.assertIn(f"End date: {tomorrow.isoformat()}", response.data["html"])
        self.assertIn("Start: 09:00", response.data["html"])
        self.assertIn("End: 10:00", response.data["html"])

        draft = AIPlanDraft.objects.get()
        self.assertEqual(
            {player.id for player in draft.target_players.all()},
            {omar.id, kareem.id},
        )
        self.assertEqual(draft.options[0]["start_date"], today.isoformat())
        self.assertEqual(draft.options[0]["end_date"], tomorrow.isoformat())

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_confirm_endpoint_creates_selected_plan_for_multiple_players(self):
        omar = make_user_with_role(
            email="omar-confirm@example.com",
            name="Omar Fatoom",
            role_name="Player",
        )
        kareem = make_user_with_role(
            email="kareem-confirm@example.com",
            name="Kareem Abo Salah",
            role_name="Player",
        )
        PlayerProfile.objects.create(user=omar, coach=self.coach, position=self.position)
        PlayerProfile.objects.create(user=kareem, coach=self.coach, position=self.position)
        with override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key"):
            with patch(
                "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
                return_value=make_plan_options_response(),
            ):
                chat_response = self.client.post(
                    CHAT_URL,
                    {"message": "Suggest 3 training plans for omar and kareem"},
                    format="json",
                )
        draft_id = chat_response.data["actions"][0]["draft_id"]

        response = self.client.post(
            CONFIRM_URL,
            {
                "action_type": "create_training_plan_from_option",
                "draft_id": draft_id,
                "selected_option_id": "option_1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        plan = TrainingPlan.objects.get()
        self.assertEqual(
            set(TrainingPlanPlayer.objects.filter(plan=plan).values_list("player_id", flat=True)),
            {omar.id, kareem.id},
        )

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_plan_suggestion_repairs_wrong_option_count_once(self):
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            side_effect=[make_one_option_response(), make_plan_options_response()],
        ) as mock_chat:
            response = self.client.post(
                CHAT_URL,
                {"message": "Suggest 3 plans for Ahmad"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["actions"]), 3)
        self.assertEqual(mock_chat.call_count, 2)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_confirm_endpoint_creates_selected_plan(self):
        draft = self._create_draft()

        response = self.client.post(
            CONFIRM_URL,
            {
                "action_type": "create_training_plan_from_option",
                "draft_id": str(draft.draft_id),
                "selected_option_id": "option_1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "success")
        plan = TrainingPlan.objects.get()
        self.assertEqual(plan.title, "Speed Plan")
        self.assertEqual(plan.creator, self.coach)
        self.assertEqual(TrainingPlanPlayer.objects.get(plan=plan).player, self.player)
        self.assertEqual(TrainingSession.objects.filter(plan=plan).count(), 2)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_coach_cannot_confirm_another_coachs_draft(self):
        draft = self._create_draft(coach=self.other_coach, player=self.other_coach_player)

        response = self.client.post(
            CONFIRM_URL,
            {
                "action_type": "create_training_plan_from_option",
                "draft_id": str(draft.draft_id),
                "selected_option_id": "option_1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(TrainingPlan.objects.count(), 0)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_expired_draft_cannot_be_used(self):
        draft = self._create_draft()
        draft.expires_at = timezone.now() - timedelta(seconds=1)
        draft.save(update_fields=["expires_at"])

        response = self.client.post(
            CONFIRM_URL,
            {
                "action_type": "create_training_plan_from_option",
                "draft_id": str(draft.draft_id),
                "selected_option_id": "option_1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Draft has expired.")
        self.assertEqual(TrainingPlan.objects.count(), 0)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_player_cannot_create_coach_plan(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.post(
            CHAT_URL,
            {"message": "Suggest 3 plans for Ahmad"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_invalid_selected_option_is_rejected(self):
        draft = self._create_draft()

        response = self.client.post(
            CONFIRM_URL,
            {
                "action_type": "create_training_plan_from_option",
                "draft_id": str(draft.draft_id),
                "selected_option_id": "option_99",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid selected option.")

    @override_settings(AI_ASSISTANT_ENABLED=False, GROQ_API_KEY="test-key")
    def test_ai_disabled_returns_clear_error(self):
        response = self.client.post(
            CHAT_URL,
            {"message": "Suggest 3 plans for Ahmad"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"detail": "AI assistant is disabled"})

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="")
    def test_missing_groq_key_returns_clear_error(self):
        response = self.client.post(
            CHAT_URL,
            {"message": "Suggest 3 plans for Ahmad"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"detail": "Missing GROQ_API_KEY."})

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_groq_invalid_response_returns_clear_error(self):
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            return_value="{bad json",
        ):
            response = self.client.post(
                CHAT_URL,
                {"message": "Suggest 3 plans for Ahmad"},
                format="json",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Groq returned an invalid plan response.")

    @override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key")
    def test_groq_timeout_returns_clear_error(self):
        with patch(
            "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
            side_effect=GroqTimeout("timeout"),
        ):
            response = self.client.post(
                CHAT_URL,
                {"message": "Suggest 3 plans for Ahmad"},
                format="json",
            )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.data["detail"], "Groq request timed out.")

    def _create_draft(self, *, coach=None, player=None):
        coach = coach or self.coach
        player = player or self.player
        if coach != self.coach:
            draft = AIPlanDraft.objects.create(
                coach=coach,
                player=player,
                options=parse_plan_options(
                    make_plan_options_response(),
                    start_date=timezone.localdate() + timedelta(days=1),
                ),
                expires_at=timezone.now() + timedelta(minutes=30),
            )
            draft.target_players.set([player])
            return draft

        with override_settings(AI_ASSISTANT_ENABLED=True, GROQ_API_KEY="test-key"):
            with patch(
                "ai_assistant.services.coach_ai_assistant_groq.GroqChatClient.chat_json",
                return_value=make_plan_options_response(),
            ):
                response = self.client.post(
                    CHAT_URL,
                    {"message": f"Suggest 3 plans for {player.first_name} {player.last_name}"},
                    format="json",
                )
        self.assertEqual(response.status_code, 200)
        return AIPlanDraft.objects.latest("created_at")


class GroqChatClientTests(TestCase):
    @override_settings(GROQ_API_KEY="test-key", GROQ_MODEL="primary-model", GROQ_FALLBACK_MODEL="")
    @patch("openai.OpenAI", return_value=Mock())
    def test_json_chat_retries_without_response_format(self, mock_openai):
        with patch.object(
            GroqChatClient,
            "_create_completion",
            side_effect=[OpenAIError("json mode unsupported"), '{"options":[] }'],
        ) as mock_create:
            response = GroqChatClient().chat_json(system_prompt="system", user_prompt="user")

        self.assertEqual(response, '{"options":[] }')
        self.assertEqual(mock_create.call_args_list[0].kwargs["use_response_format"], True)
        self.assertEqual(mock_create.call_args_list[1].kwargs["use_response_format"], False)

    @override_settings(GROQ_API_KEY="test-key", GROQ_MODEL="primary-model", GROQ_FALLBACK_MODEL="")
    @patch("openai.OpenAI", return_value=Mock())
    def test_service_unavailable_includes_safe_provider_status(self, mock_openai):
        error = OpenAIError("bad request")
        error.status_code = 400
        with patch.object(GroqChatClient, "_create_completion", side_effect=error):
            with self.assertRaises(GroqServiceUnavailable) as caught:
                GroqChatClient().chat_json(system_prompt="system", user_prompt="user")

        self.assertEqual(str(caught.exception), "Groq service is unavailable. Provider status: 400.")
