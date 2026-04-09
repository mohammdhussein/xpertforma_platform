from datetime import date
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PasswordSetupToken, PlayerProfile, Position, Role, User, UserRole


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_SETUP_DEEP_LINK_BASE="https://app.xpertforma.com/set-password",
    DEFAULT_FROM_EMAIL="no-reply@xpertforma.com",
)
class CoachCreatePlayerFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.coach_role = Role.objects.create(role_name="Coach")
        self.player_role = Role.objects.create(role_name="Player")
        self.coach = User.objects.create_user(
            email="coach@example.com",
            password="StrongPass123!",
            name="Coach One",
        )
        UserRole.objects.create(user=self.coach, role=self.coach_role)
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")
        self.striker = Position.objects.get(code="ST")
        self.central_midfielder = Position.objects.get(code="CM")
        self.right_winger = Position.objects.get(code="RW")
        self.client.force_authenticate(user=self.coach)

    def test_create_player_sends_password_setup_email_with_deep_link(self):
        response = self.client.post(
            "/api/coach/create-player/",
            {
                "name": "Player One",
                "email": "player1@example.com",
                "position_id": self.striker.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["created"])
        self.assertTrue(response.data["password_setup_required"])
        self.assertIn("deep_link", response.data["setup_password"])
        self.assertIn("expires_at", response.data["setup_password"])
        self.assertEqual(
            response.data["position"],
            {"id": self.striker.id, "name": self.striker.name, "code": self.striker.code},
        )

        player = User.objects.get(email="player1@example.com")
        token_record = PasswordSetupToken.objects.get(user=player)
        self.assertTrue(hasattr(player, "player_profile"))
        self.assertEqual(player.player_profile.coach, self.coach)
        self.assertEqual(player.player_profile.login_status, "first_login")
        self.assertEqual(player.player_profile.position, self.striker)
        self.assertIsNone(player.phone)
        self.assertIsNone(player.date_of_birth)
        self.assertIsNone(player.player_profile.height_cm)
        self.assertIsNone(player.player_profile.weight_kg)
        self.assertIsNone(player.player_profile.foot)
        self.assertEqual(player.player_profile.state, PlayerProfile.STATE_ACTIVE)
        self.assertEqual(player.player_profile.fitness_level, "")
        self.assertFalse(token_record.is_used)
        self.assertEqual(token_record.purpose, PasswordSetupToken.PURPOSE_SET_PASSWORD)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["player1@example.com"])
        self.assertIn("https://app.xpertforma.com/set-password?token=", mail.outbox[0].body)
        self.assertNotIn("uid=", mail.outbox[0].body)

        deep_link = response.data["setup_password"]["deep_link"]
        parsed_link = urlparse(deep_link)
        query = parse_qs(parsed_link.query)
        self.assertEqual(parsed_link.scheme, "https")
        self.assertEqual(parsed_link.netloc, "app.xpertforma.com")
        self.assertEqual(parsed_link.path, "/set-password")
        self.assertEqual(sorted(query.keys()), ["token"])
        self.assertEqual(len(query["token"][0]), 43)

    def test_existing_player_is_reassigned_without_duplicate_user(self):
        old_coach = User.objects.create_user(
            email="oldcoach@example.com",
            password="StrongPass123!",
            name="Old Coach",
        )
        UserRole.objects.create(user=old_coach, role=self.coach_role)
        CoachProfile.objects.create(user=old_coach, approval_status="APPROVED")
        player = User.objects.create_user(
            email="player2@example.com",
            password="StrongPass123!",
            name="Existing Player",
            phone="0509990000",
            date_of_birth=date(2002, 1, 2),
        )
        UserRole.objects.create(user=player, role=self.player_role)
        PlayerProfile.objects.create(
            user=player,
            coach=old_coach,
            position=self.right_winger,
            login_status="complete",
            height_cm=174,
            weight_kg=67,
            foot=PlayerProfile.FOOT_RIGHT,
            state=PlayerProfile.STATE_NEEDS_REVIEW,
            fitness_level="starter",
        )

        response = self.client.post(
            "/api/coach/create-player/",
            {
                "name": "Existing Player",
                "email": "player2@example.com",
                "position_id": self.central_midfielder.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["created"])
        self.assertFalse(response.data["password_setup_required"])
        self.assertIsNone(response.data["setup_password"])
        self.assertFalse(response.data["invitation_sent"])
        self.assertEqual(len(mail.outbox), 0)

        player.refresh_from_db()
        self.assertEqual(player.player_profile.coach, self.coach)
        self.assertEqual(player.phone, "0509990000")
        self.assertEqual(player.date_of_birth, date(2002, 1, 2))
        self.assertEqual(player.player_profile.position, self.central_midfielder)
        self.assertEqual(player.player_profile.height_cm, 174)
        self.assertEqual(player.player_profile.weight_kg, 67)
        self.assertEqual(player.player_profile.foot, PlayerProfile.FOOT_RIGHT)
        self.assertEqual(player.player_profile.state, PlayerProfile.STATE_NEEDS_REVIEW)
        self.assertEqual(player.player_profile.fitness_level, "starter")
        self.assertEqual(
            response.data["position"],
            {
                "id": self.central_midfielder.id,
                "name": self.central_midfielder.name,
                "code": self.central_midfielder.code,
            },
        )

    def test_reassign_keeps_optional_profile_values_when_omitted(self):
        old_coach = User.objects.create_user(
            email="keepercoach@example.com",
            password="StrongPass123!",
            name="Keeper Coach",
        )
        UserRole.objects.create(user=old_coach, role=self.coach_role)
        CoachProfile.objects.create(user=old_coach, approval_status="APPROVED")
        player = User.objects.create_user(
            email="player4@example.com",
            password="StrongPass123!",
            name="Stable Player",
            phone="0505556666",
            date_of_birth=date(2003, 1, 2),
        )
        UserRole.objects.create(user=player, role=self.player_role)
        PlayerProfile.objects.create(
            user=player,
            coach=old_coach,
            position=self.right_winger,
            login_status="complete",
            height_cm=177,
            weight_kg=70,
            foot=PlayerProfile.FOOT_RIGHT,
            state=PlayerProfile.STATE_NEEDS_REVIEW,
            fitness_level="elite",
        )

        response = self.client.post(
            "/api/coach/create-player/",
            {
                "name": "Stable Player",
                "email": "player4@example.com",
                "position_id": self.right_winger.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        player.refresh_from_db()
        self.assertEqual(player.player_profile.coach, self.coach)
        self.assertEqual(player.phone, "0505556666")
        self.assertEqual(player.date_of_birth, date(2003, 1, 2))
        self.assertEqual(player.player_profile.position, self.right_winger)
        self.assertEqual(player.player_profile.height_cm, 177)
        self.assertEqual(player.player_profile.weight_kg, 70)
        self.assertEqual(player.player_profile.foot, PlayerProfile.FOOT_RIGHT)
        self.assertEqual(player.player_profile.state, PlayerProfile.STATE_NEEDS_REVIEW)
        self.assertEqual(player.player_profile.fitness_level, "elite")

    def test_duplicate_player_for_same_coach_returns_conflict(self):
        player = User.objects.create_user(
            email="player3@example.com",
            password="StrongPass123!",
            name="Existing Same Coach Player",
        )
        UserRole.objects.create(user=player, role=self.player_role)
        PlayerProfile.objects.create(
            user=player,
            coach=self.coach,
            position=self.striker,
            login_status="complete",
        )

        response = self.client.post(
            "/api/coach/create-player/",
            {
                "name": "Existing Same Coach Player",
                "email": "player3@example.com",
                "position_id": self.striker.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)

