from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PasswordSetupToken, PlayerProfile, Role, User, UserRole
from accounts.services.password_setup import create_password_setup_token


class PasswordSetupTokenServiceTests(TestCase):
    def setUp(self):
        self.player = User.objects.create_user(
            email="invitee@example.com",
            password=None,
            name="Invitee",
        )
        player_role, _ = Role.objects.get_or_create(role_name="Player")
        UserRole.objects.create(user=self.player, role=player_role)
        PlayerProfile.objects.create(user=self.player, login_status="first_login")

    def test_token_creation_invalidates_previous_unused_tokens(self):
        first_record, first_raw_token = create_password_setup_token(self.player)
        second_record, second_raw_token = create_password_setup_token(self.player)

        first_record.refresh_from_db()
        second_record.refresh_from_db()

        self.assertNotEqual(first_raw_token, second_raw_token)
        self.assertEqual(first_record.purpose, PasswordSetupToken.PURPOSE_SET_PASSWORD)
        self.assertFalse(second_record.is_used)
        self.assertTrue(first_record.expires_at <= timezone.now())
        self.assertTrue(second_record.expires_at > timezone.now())
        self.assertNotEqual(second_record.token, second_raw_token)


class CompleteSetPasswordTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player = User.objects.create_user(
            email="invitee@example.com",
            password=None,
            name="Invitee",
        )
        player_role, _ = Role.objects.get_or_create(role_name="Player")
        UserRole.objects.create(user=self.player, role=player_role)
        PlayerProfile.objects.create(user=self.player, login_status="first_login")

    def test_player_can_set_password_with_valid_token(self):
        token_record, raw_token = create_password_setup_token(self.player)

        response = self.client.post(
            reverse("complete-set-password"),
            {
                "token": raw_token,
                "password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        token_record.refresh_from_db()
        self.assertTrue(self.player.check_password("NewStrongPass123!"))
        self.assertEqual(self.player.player_profile.login_status, "first_login")
        self.assertIsNone(self.player.date_of_birth)
        self.assertIsNone(self.player.phone)
        self.assertIsNone(self.player.player_profile.position)
        self.assertIsNone(self.player.player_profile.foot)
        self.assertEqual(self.player.player_profile.state, PlayerProfile.STATE_ACTIVE)
        self.assertTrue(token_record.is_used)

    def test_expired_token_returns_error(self):
        token_record, raw_token = create_password_setup_token(self.player)
        token_record.expires_at = timezone.now() - timedelta(minutes=1)
        token_record.save(update_fields=["expires_at"])

        response = self.client.post(
            reverse("complete-set-password"),
            {
                "token": raw_token,
                "password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["token"], ["Token has expired."])

    def test_token_cannot_be_reused(self):
        _, raw_token = create_password_setup_token(self.player)

        first_response = self.client.post(
            reverse("complete-set-password"),
            {
                "token": raw_token,
                "password": "NewStrongPass123!",
            },
            format="json",
        )
        second_response = self.client.post(
            reverse("complete-set-password"),
            {
                "token": raw_token,
                "password": "AnotherStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(second_response.data["token"], ["Token has already been used."])

    def test_invalid_token_returns_error(self):
        response = self.client.post(
            reverse("complete-set-password"),
            {
                "token": "invalid-token",
                "password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["token"], ["Invalid token."])
