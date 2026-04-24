from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole


class CoachPlayerStateAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.coach_role = Role.objects.create(role_name="Coach")
        self.player_role = Role.objects.create(role_name="Player")
        self.position = Position.objects.get(code="ST")

        self.coach = User.objects.create_user(
            email="statecoach@example.com",
            password="StrongPass123!",
            name="State Coach",
        )
        UserRole.objects.create(user=self.coach, role=self.coach_role)
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")

        self.other_coach = User.objects.create_user(
            email="otherstatecoach@example.com",
            password="StrongPass123!",
            name="Other Coach",
        )
        UserRole.objects.create(user=self.other_coach, role=self.coach_role)
        CoachProfile.objects.create(user=self.other_coach, approval_status="APPROVED")

        self.player = User.objects.create_user(
            email="stateplayer@example.com",
            password="StrongPass123!",
            name="State Player",
        )
        UserRole.objects.create(user=self.player, role=self.player_role)
        PlayerProfile.objects.create(
            user=self.player,
            coach=self.coach,
            position=self.position,
            state=PlayerProfile.STATE_ACTIVE,
        )

        self.client.force_authenticate(user=self.coach)

    def test_coach_can_mark_player_injured_without_expected_return_date(self):
        response = self.client.patch(
            f"/api/coach/players/{self.player.id}/state/",
            {"state": "INJURED"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.player.player_profile.refresh_from_db()
        self.assertEqual(self.player.player_profile.state, PlayerProfile.STATE_INJURED)
        self.assertIsNone(self.player.player_profile.expected_return_date)
        self.assertEqual(
            response.data,
            {
                "player_id": str(self.player.id),
                "state": "INJURED",
                "expected_return_date": None,
                "needs_attention": True,
            },
        )

    def test_coach_can_mark_player_injured_with_expected_return_date(self):
        response = self.client.patch(
            f"/api/coach/players/{self.player.id}/state/",
            {
                "state": "INJURED",
                "expected_return_date": "2026-05-10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.player.player_profile.refresh_from_db()
        self.assertEqual(self.player.player_profile.state, PlayerProfile.STATE_INJURED)
        self.assertEqual(self.player.player_profile.expected_return_date, date(2026, 5, 10))
        self.assertEqual(response.data["expected_return_date"], "2026-05-10")
        self.assertTrue(response.data["needs_attention"])

    def test_coach_can_mark_player_active_and_clear_expected_return_date(self):
        profile = self.player.player_profile
        profile.state = PlayerProfile.STATE_INJURED
        profile.expected_return_date = date(2026, 5, 10)
        profile.save(update_fields=["state", "expected_return_date"])

        response = self.client.patch(
            f"/api/coach/players/{self.player.id}/state/",
            {"state": "ACTIVE"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.state, PlayerProfile.STATE_ACTIVE)
        self.assertIsNone(profile.expected_return_date)
        self.assertEqual(response.data["state"], "ACTIVE")
        self.assertIsNone(response.data["expected_return_date"])
        self.assertFalse(response.data["needs_attention"])

    def test_state_endpoint_rejects_lowercase_state(self):
        response = self.client.patch(
            f"/api/coach/players/{self.player.id}/state/",
            {"state": "injured"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid state. Use uppercase values.")
        self.assertEqual(list(response.data["expected"]), ["ACTIVE", "INJURED"])

    def test_state_endpoint_rejects_invalid_expected_return_date_format(self):
        response = self.client.patch(
            f"/api/coach/players/{self.player.id}/state/",
            {
                "state": "INJURED",
                "expected_return_date": "10-05-2026",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid expected_return_date format.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_state_endpoint_rejects_expected_return_date_for_active_state(self):
        response = self.client.patch(
            f"/api/coach/players/{self.player.id}/state/",
            {
                "state": "ACTIVE",
                "expected_return_date": "2026-05-10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "expected_return_date is only allowed when state is INJURED.")

    def test_state_endpoint_returns_not_found_for_other_coach_player(self):
        other_player = User.objects.create_user(
            email="otherstateplayer@example.com",
            password="StrongPass123!",
            name="Other State Player",
        )
        UserRole.objects.create(user=other_player, role=self.player_role)
        PlayerProfile.objects.create(
            user=other_player,
            coach=self.other_coach,
            position=self.position,
        )

        response = self.client.patch(
            f"/api/coach/players/{other_player.id}/state/",
            {"state": "INJURED"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_state_endpoint_requires_coach_user(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.patch(
            f"/api/coach/players/{self.player.id}/state/",
            {"state": "INJURED"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
