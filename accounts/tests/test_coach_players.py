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
            age=19,
            phone="0501234567",
            foot=PlayerProfile.FOOT_RIGHT,
            state=PlayerProfile.STATE_INJURED,
            avatar="player_avatars/alpha.png",
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
            state=PlayerProfile.STATE_NEEDS_REVIEW,
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
                "state": PlayerProfile.STATE_INJURED,
                "avatar_url": "/media/player_avatars/alpha.png",
            },
        )

    def test_players_endpoint_filters_by_state_tab(self):
        response = self.client.get("/api/coach/players/?tab=needs_review")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["players"]), 1)
        self.assertEqual(response.data["players"][0]["id"], str(self.player_two.id))
        self.assertEqual(response.data["players"][0]["state"], PlayerProfile.STATE_NEEDS_REVIEW)

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
        self.assertEqual(response.data["age"], 19)
        self.assertEqual(response.data["phone"], "0501234567")
        self.assertEqual(response.data["foot"], PlayerProfile.FOOT_RIGHT)
        self.assertEqual(response.data["state"], PlayerProfile.STATE_INJURED)
        self.assertEqual(
            response.data["position"],
            {"id": self.striker.id, "name": self.striker.name, "code": self.striker.code},
        )

