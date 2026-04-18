from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole


class UserInfoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        player_role = Role.objects.create(role_name="Player")
        self.striker = Position.objects.get(code="ST")
        self.player = User.objects.create_user(
            email="seenplayer@example.com",
            password="StrongPass123!",
            name="Seen Player",
        )
        UserRole.objects.create(user=self.player, role=player_role)
        PlayerProfile.objects.create(
            user=self.player,
            position=self.striker,
            login_status="COMPLETE",
        )

    def test_authenticated_request_updates_last_seen(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.get("/api/user-info/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["player"]["position"],
            {"id": self.striker.id, "name": self.striker.name, "code": self.striker.code},
        )
        self.player.refresh_from_db()
        self.assertIsNotNone(self.player.last_seen_at)

    def test_coach_user_info_returns_coach_payload(self):
        coach_role = Role.objects.create(role_name="Coach")
        coach = User.objects.create_user(
            email="coachinfo@example.com",
            password="StrongPass123!",
            name="Coach Info",
        )
        UserRole.objects.create(user=coach, role=coach_role)
        approved_at = timezone.now()
        CoachProfile.objects.create(
            user=coach,
            approval_status="APPROVED",
            approved_at=approved_at,
            rejection_reason="",
        )

        self.client.force_authenticate(user=coach)

        response = self.client.get("/api/user-info/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "Coach")
        self.assertEqual(
            response.data["coach"],
            {
                "approval_status": "APPROVED",
                "certificate_image": None,
                "approved_at": approved_at.isoformat().replace("+00:00", "Z"),
                "rejection_reason": "",
            },
        )
        self.assertNotIn("player", response.data)

