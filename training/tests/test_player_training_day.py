from datetime import time

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import PlayerProfile, Position, Role, User, UserRole
from training.models import PlayerSessionProgress, TrainingPlan, TrainingPlanPlayer, TrainingSession


class PlayerTrainingDayTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        player_role = Role.objects.create(role_name="Player")
        self.player = User.objects.create_user(
            email="dayplayer@example.com",
            password="StrongPass123!",
            name="Day Player",
        )
        UserRole.objects.create(user=self.player, role=player_role)
        striker = Position.objects.get(code="ST")
        PlayerProfile.objects.create(
            user=self.player,
            position=striker,
            login_status="complete",
        )
        self.plan = TrainingPlan.objects.create(
            creator=self.player,
            title="Daily Plan",
            start_date="2026-04-01",
            end_date="2026-04-03",
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player, assigned_by=self.player)
        self.first_session = TrainingSession.objects.create(
            plan=self.plan,
            title="Speed Session",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        TrainingSession.objects.create(
            plan=self.plan,
            title="Strength Session",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(12, 0),
            end_time=time(12, 45),
        )
        PlayerSessionProgress.objects.create(
            player=self.player,
            session=self.first_session,
            status="completed",
        )
        self.client.force_authenticate(user=self.player)

    def test_training_day_groups_sessions_and_counts_completed_items(self):
        response = self.client.get("/api/player/training/day/", {"date": "2026-04-01"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["date"], "2026-04-01")
        self.assertEqual(response.data["summary"]["completed_sessions"], 1)
        self.assertEqual(response.data["summary"]["total_sessions"], 2)
        self.assertEqual(response.data["summary"]["total_duration_min"], 105)
        self.assertEqual(len(response.data["plans"]), 1)
        self.assertEqual(response.data["plans"][0]["sessions_count"], 2)
        self.assertFalse(response.data["plans"][0]["completed"])
        self.assertEqual(response.data["plans"][0]["sessions"][0]["status"], "completed")

    def test_training_day_rejects_invalid_date_format(self):
        response = self.client.get("/api/player/training/day/", {"date": "bad-date"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Invalid date format. Use YYYY-MM-DD."})

