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
        CoachProfile.objects.create(user=coach, approval_status="PENDING")

        response = self.client.post(
            "/api/auth/login/",
            {"email": coach.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                "coach_status": {
                    "detail": "Coach account is pending approval.",
                    "expected": ["APPROVED"],
                    "register_status": "PENDING",
                }
            },
        )

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
            login_status="COMPLETE",
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

    def test_logout_blacklists_refresh_token_and_refresh_fails_afterward(self):
        player = User.objects.create_user(
            email="logoutplayer@example.com",
            password="StrongPass123!",
            name="Logout Player",
        )
        UserRole.objects.create(user=player, role=self.player_role)
        PlayerProfile.objects.create(
            user=player,
            position=self.striker,
            login_status="COMPLETE",
        )

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": player.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        access_token = login_response.data["access"]
        refresh_token = login_response.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = self.client.post(
            "/api/auth/logout/",
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(logout_response.status_code, 205)

        refresh_response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, 401)

    def test_revoked_coach_approval_blocks_coach_business_endpoints_even_with_existing_token(self):
        coach = User.objects.create_user(
            email="approvedcoach@example.com",
            password="StrongPass123!",
            name="Approved Coach",
        )
        UserRole.objects.create(user=coach, role=self.coach_role)
        coach_profile = CoachProfile.objects.create(user=coach, approval_status="APPROVED")

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": coach.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)

        coach_profile.approval_status = "REJECTED"
        coach_profile.save(update_fields=["approval_status"])

        access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        players_response = self.client.get("/api/coach/players/")
        self.assertEqual(players_response.status_code, 403)

        create_player_response = self.client.post(
            "/api/coach/create-player/",
            {
                "name": "Blocked Player",
                "email": "blockedplayer@example.com",
                "position_id": self.striker.id,
            },
            format="json",
        )
        self.assertEqual(create_player_response.status_code, 403)

        plans_response = self.client.get("/api/coach/plans/")
        self.assertEqual(plans_response.status_code, 403)
