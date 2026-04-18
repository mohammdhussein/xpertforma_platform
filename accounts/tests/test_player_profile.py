from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole


class PlayerProfileEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player_role = Role.objects.create(role_name="Player")
        self.coach_role = Role.objects.create(role_name="Coach")
        self.striker = Position.objects.get(code="ST")
        self.center_forward = Position.objects.get(code="CF")

        self.player = User.objects.create_user(
            email="profileplayer@example.com",
            password="StrongPass123!",
            name="Profile Player",
        )
        UserRole.objects.create(user=self.player, role=self.player_role)
        PlayerProfile.objects.create(
            user=self.player,
            login_status="FIRST_LOGIN",
        )

    def test_get_returns_current_player_profile(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.get("/api/player/profile/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.player.id))
        self.assertEqual(response.data["email"], self.player.email)
        self.assertEqual(response.data["login_status"], "FIRST_LOGIN")
        self.assertEqual(response.data["position"], {"id": None, "name": "", "code": None})
        self.assertIsNone(response.data["team_id"])
        self.assertIsNone(response.data["avatar_url"])
        self.assertIsNone(response.data["height_cm"])
        self.assertIsNone(response.data["weight_kg"])
        self.assertIsNone(response.data["date_of_birth"])
        self.assertIsNone(response.data["phone"])
        self.assertIsNone(response.data["foot"])

    def test_patch_updates_profile_and_marks_onboarding_complete(self):
        self.player.player_profile.position = self.striker
        self.player.player_profile.save(update_fields=["position"])
        self.client.force_authenticate(user=self.player)

        response = self.client.patch(
            "/api/player/profile/",
            {
                "height_cm": 182.5,
                "weight_kg": 76.2,
                "date_of_birth": "2008-04-09",
                "phone": "0501112222",
                "foot": "BOTH",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.player.player_profile.refresh_from_db()
        self.assertEqual(self.player.player_profile.login_status, "COMPLETE")
        self.assertEqual(self.player.player_profile.position, self.striker)
        self.assertEqual(self.player.player_profile.height_cm, 182.5)
        self.assertEqual(self.player.player_profile.weight_kg, 76.2)
        self.assertEqual(self.player.date_of_birth.isoformat(), "2008-04-09")
        self.assertEqual(self.player.phone, "0501112222")
        self.assertEqual(self.player.player_profile.foot, PlayerProfile.FOOT_BOTH)
        self.assertEqual(
            response.data["position"],
            {"id": self.striker.id, "name": self.striker.name, "code": self.striker.code},
        )
        self.assertEqual(response.data["height_cm"], 182.5)
        self.assertEqual(response.data["weight_kg"], 76.2)
        self.assertEqual(response.data["date_of_birth"], "2008-04-09")
        self.assertEqual(response.data["phone"], "0501112222")
        self.assertEqual(response.data["login_status"], "COMPLETE")
        self.assertEqual(response.data["foot"], "BOTH")

    def test_put_accepts_partial_profile_payload_without_marking_complete(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.put(
            "/api/player/profile/",
            {
                "height_cm": 180,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.player.player_profile.refresh_from_db()
        self.assertEqual(self.player.player_profile.login_status, "FIRST_LOGIN")
        self.assertIsNone(self.player.player_profile.position)
        self.assertEqual(self.player.player_profile.height_cm, 180)
        self.assertIsNone(self.player.date_of_birth)
        self.assertIsNone(self.player.phone)
        self.assertIsNone(self.player.player_profile.foot)
        self.assertIsNone(self.player.player_profile.weight_kg)
        self.assertEqual(response.data["login_status"], "FIRST_LOGIN")

    def test_profile_update_rejects_removed_fields(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.patch(
            "/api/player/profile/",
            {
                "position_id": self.center_forward.id,
                "state": PlayerProfile.STATE_INJURED,
                "fitness_level": "intermediate",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("position_id", response.data)
        self.assertIn("state", response.data)
        self.assertIn("fitness_level", response.data)

    def test_profile_update_rejects_lowercase_foot(self):
        self.client.force_authenticate(user=self.player)

        response = self.client.patch(
            "/api/player/profile/",
            {"foot": "both"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["foot"], ["Use uppercase values."])

    def test_player_profile_endpoint_requires_player_user(self):
        coach = User.objects.create_user(
            email="profilecoach@example.com",
            password="StrongPass123!",
            name="Profile Coach",
        )
        UserRole.objects.create(user=coach, role=self.coach_role)
        CoachProfile.objects.create(user=coach, approval_status="APPROVED")
        self.client.force_authenticate(user=coach)

        response = self.client.patch(
            "/api/player/profile/",
            {
                "height_cm": 182,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
