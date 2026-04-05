from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import TrainingPlan, TrainingPlanPlayer


class CoachPlayersListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.coach_role = Role.objects.create(role_name="Coach")
        self.player_role = Role.objects.create(role_name="Player")
        self.coach = User.objects.create_user(
            email="playerscoach@example.com",
            password="StrongPass123!",
            name="Players Coach",
        )
        UserRole.objects.create(user=self.coach, role=self.coach_role)
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")
        self.striker = Position.objects.get(code="ST")
        self.central_midfielder = Position.objects.get(code="CM")

        self.player_one = User.objects.create_user(
            email="alpha@example.com",
            password="StrongPass123!",
            name="Alpha Player",
        )
        UserRole.objects.create(user=self.player_one, role=self.player_role)
        PlayerProfile.objects.create(
            user=self.player_one,
            coach=self.coach,
            position=self.striker,
            position_label=self.striker.name,
        )

        self.player_two = User.objects.create_user(
            email="beta@example.com",
            password="StrongPass123!",
            name="Beta Player",
        )
        UserRole.objects.create(user=self.player_two, role=self.player_role)
        PlayerProfile.objects.create(
            user=self.player_two,
            coach=self.coach,
            position=self.central_midfielder,
            position_label=self.central_midfielder.name,
        )

        self.client.force_authenticate(user=self.coach)

    def test_players_endpoint_returns_simplified_players_list(self):
        response = self.client.get("/api/coach/players/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.data.keys()), ["players"])
        self.assertEqual(len(response.data["players"]), 2)
        self.assertEqual(
            response.data["players"][0],
            {
                "id": str(self.player_one.id),
                "name": "Alpha Player",
                "position": {
                    "id": self.striker.id,
                    "name": self.striker.name,
                    "code": self.striker.code,
                },
                "state": "active",
            },
        )

    def test_player_profile_endpoint_uses_shorter_path(self):
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Profile Plan",
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=7),
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player_one, assigned_by=self.coach)

        response = self.client.get(f"/api/coach/players/{self.player_one.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.player_one.id))
        self.assertEqual(
            response.data["position"],
            {"id": self.striker.id, "name": self.striker.name, "code": self.striker.code},
        )

