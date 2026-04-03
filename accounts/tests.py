from datetime import time, timedelta

from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import TrainingPlan, TrainingPlanPlayer, TrainingSession


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

    def test_create_player_returns_setup_token_for_new_user(self):
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
        self.assertIn("uid", response.data["setup_password"])
        self.assertIn("token", response.data["setup_password"])
        self.assertEqual(
            response.data["position"],
            {"id": self.striker.id, "name": self.striker.name, "code": self.striker.code},
        )

        player = User.objects.get(email="player1@example.com")
        self.assertTrue(hasattr(player, "player_profile"))
        self.assertEqual(player.player_profile.coach, self.coach)
        self.assertEqual(player.player_profile.login_status, "first_login")
        self.assertEqual(player.player_profile.position, self.striker)

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


class PlayerSetPasswordTests(TestCase):
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
        uid = urlsafe_base64_encode(force_bytes(self.player.pk))
        token = default_token_generator.make_token(self.player)

        response = self.client.post(
            reverse("player-set-password"),
            {
                "uid": uid,
                "token": token,
                "password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.assertTrue(self.player.check_password("NewStrongPass123!"))
        self.assertEqual(self.player.player_profile.login_status, "complete")


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
