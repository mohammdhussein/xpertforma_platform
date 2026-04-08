from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import PlayerProfile, Position, Role, User, UserRole
from training.models import TrainingPlan, TrainingPlanPlayer, TrainingSession


class PlayerSessionStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        player_role = Role.objects.create(role_name="Player")
        self.player = User.objects.create_user(
            email="statusplayer@example.com",
            password="StrongPass123!",
            name="Status Player",
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
            title="Status Plan",
            start_date="2026-04-01",
            end_date="2026-04-03",
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player, assigned_by=self.player)
        self.session = TrainingSession.objects.create(
            plan=self.plan,
            title="Status Session",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )
        self.client.force_authenticate(user=self.player)

    def test_status_endpoint_updates_session_status(self):
        response = self.client.post(
            f"/api/player/training/sessions/{self.session.session_id}/status/",
            {"status": "completed"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"session_id": str(self.session.session_id), "status": "completed"},
        )

    def test_status_endpoint_rejects_unknown_status(self):
        response = self.client.post(
            f"/api/player/training/sessions/{self.session.session_id}/status/",
            {"status": "paused"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Invalid status."})
