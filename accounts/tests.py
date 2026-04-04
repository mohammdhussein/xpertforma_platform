from datetime import time, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PasswordSetupToken, PlayerProfile, Position, Role, User, UserRole
from accounts.services.password_setup import create_password_setup_token
from training.models import TrainingPlan, TrainingPlanPlayer, TrainingSession


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
        )
        UserRole.objects.create(user=player, role=self.player_role)
        PlayerProfile.objects.create(
            user=player,
            coach=old_coach,
            position=self.right_winger,
            position_label=self.right_winger.name,
            login_status="complete",
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
        self.assertEqual(player.player_profile.position, self.central_midfielder)
        self.assertEqual(player.player_profile.position_label, self.central_midfielder.name)
        self.assertEqual(
            response.data["position"],
            {
                "id": self.central_midfielder.id,
                "name": self.central_midfielder.name,
                "code": self.central_midfielder.code,
            },
        )

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
            position_label=self.striker.name,
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
        self.assertEqual(self.player.player_profile.login_status, "complete")
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


class CoachDashboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.coach_role = Role.objects.create(role_name="Coach")
        self.player_role = Role.objects.create(role_name="Player")

        self.coach = User.objects.create_user(
            email="dashcoach@example.com",
            password="StrongPass123!",
            name="Dash Coach",
        )
        UserRole.objects.create(user=self.coach, role=self.coach_role)
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")

        self.player = User.objects.create_user(
            email="dashplayer@example.com",
            password="StrongPass123!",
            name="Dash Player",
        )
        UserRole.objects.create(user=self.player, role=self.player_role)
        self.central_midfielder = Position.objects.get(code="CM")
        PlayerProfile.objects.create(
            user=self.player,
            coach=self.coach,
            position=self.central_midfielder,
            position_label=self.central_midfielder.name,
        )
        self.player.last_seen_at = timezone.now()
        self.player.save(update_fields=["last_seen_at"])

        self.client.force_authenticate(user=self.coach)

    def test_dashboard_returns_top_three_upcoming_sessions(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Dashboard Plan",
            start_date=today,
            end_date=today + timedelta(days=10),
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        created_titles = []
        for index in range(4):
            title = f"Session {index + 1}"
            TrainingSession.objects.create(
                plan=plan,
                title=title,
                session_date=today + timedelta(days=index),
                session_type=TrainingSession.SESSION_TYPE_TEAM if index == 0 else TrainingSession.SESSION_TYPE_GROUP,
                start_time=time(9 + index, 0),
                end_time=time(10 + index, 0),
            )
            created_titles.append(title)

        response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["upcoming_sessions"]), 3)
        self.assertEqual(
            [session["title"] for session in response.data["upcoming_sessions"]],
            created_titles[:3],
        )
        self.assertEqual(
            response.data["my_players"][0]["position"],
            {
                "id": self.central_midfielder.id,
                "name": self.central_midfielder.name,
                "code": self.central_midfielder.code,
            },
        )
        self.assertEqual(response.data["my_players"][0]["last_activity"], self.player.last_seen_at.isoformat().replace("+00:00", "Z"))
        self.assertEqual(response.data["upcoming_sessions"][0]["session_type"], TrainingSession.SESSION_TYPE_TEAM)

    def test_dashboard_counts_sessions_this_week_from_sunday(self):
        mocked_today = timezone.datetime(2026, 4, 8).date()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Weekly Count Plan",
            start_date=mocked_today - timedelta(days=3),
            end_date=mocked_today + timedelta(days=7),
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        TrainingSession.objects.create(
            plan=plan,
            title="Sunday Session",
            session_date=timezone.datetime(2026, 4, 5).date(),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Saturday Session",
            session_date=timezone.datetime(2026, 4, 11).date(),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(11, 0),
            end_time=time(12, 0),
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Next Sunday Session",
            session_date=timezone.datetime(2026, 4, 12).date(),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(13, 0),
            end_time=time(14, 0),
        )

        with patch("accounts.views.coach_dashboard.timezone.localdate", return_value=mocked_today):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stats"]["sessions_this_week"], 2)


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


class LastSeenMiddlewareTests(TestCase):
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
            position_label=self.striker.name,
            login_status="complete",
        )
        self.client.force_authenticate(user=self.player)

    def test_authenticated_request_updates_last_seen(self):
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


class PositionListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        player_role = Role.objects.create(role_name="Player")
        self.player = User.objects.create_user(
            email="positions@example.com",
            password="StrongPass123!",
            name="Positions User",
        )
        UserRole.objects.create(user=self.player, role=player_role)
        self.client.force_authenticate(user=self.player)

    def test_positions_endpoint_returns_seeded_positions(self):
        response = self.client.get("/api/positions/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["positions"]), 13)
        self.assertEqual(response.data["positions"][0]["name"], "Goalkeeper")
        self.assertEqual(response.data["positions"][-1]["code"], "CF")
