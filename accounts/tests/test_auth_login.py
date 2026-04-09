from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole


class LoginEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.coach_role = Role.objects.create(role_name="Coach")
        self.player_role = Role.objects.create(role_name="Player")
        self.striker = Position.objects.get(code="ST")

    def test_pending_coach_login_returns_nested_coach_status_error(self):
        coach = User.objects.create_user(
            email="pendingcoach@example.com",
            password="StrongPass123!",
            name="Pending Coach",
        )
        UserRole.objects.create(user=coach, role=self.coach_role)
        CoachProfile.objects.create(user=coach, approval_status="pending")

        response = self.client.post(
            "/api/auth/login/",
            {"email": coach.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"coach_status": {"register_status": "PENDING"}})

    def test_player_login_returns_uppercase_login_status(self):
        player = User.objects.create_user(
            email="playerlogin@example.com",
            password="StrongPass123!",
            name="Player Login",
        )
        UserRole.objects.create(user=player, role=self.player_role)
        PlayerProfile.objects.create(
            user=player,
            position=self.striker,
            login_status="complete",
        )

        response = self.client.post(
            "/api/auth/login/",
            {"email": player.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["player_status"],
            {
                "has_coach": False,
                "login_status": "COMPLETE",
            },
        )
