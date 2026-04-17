from datetime import time, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PlayerProfile, Position, Role, User, UserRole
from training.models import PlayerSessionProgress, TrainingPlan, TrainingPlanPlayer, TrainingSession


class PlayerDashboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        player_role = Role.objects.create(role_name="Player")
        self.player = User.objects.create_user(
            email="dashboardplayer@example.com",
            password="StrongPass123!",
            name="Dashboard Player",
        )
        UserRole.objects.create(user=self.player, role=player_role)
        striker = Position.objects.get(code="ST")
        PlayerProfile.objects.create(
            user=self.player,
            position=striker,
            login_status="complete",
        )
        self.client.force_authenticate(user=self.player)

    def test_dashboard_returns_uppercase_session_status(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.player,
            title="Dashboard Plan",
            start_date=today,
            end_date=today + timedelta(days=1),
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.player)
        session = TrainingSession.objects.create(
            plan=plan,
            title="Finishing",
            session_date=today,
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(23, 0),
            end_time=time(23, 30),
        )
        PlayerSessionProgress.objects.create(
            player=self.player,
            session=session,
            status="complete",
        )

        response = self.client.get("/api/player/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session"]["status"], "COMPLETED")
