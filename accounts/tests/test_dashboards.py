from datetime import time, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import TrainingPlan, TrainingPlanPlayer, TrainingSession


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
        mocked_now = timezone.datetime(2026, 4, 8, 8, 0, tzinfo=dt_timezone.utc)
        today = mocked_now.date()
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

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
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
        self.assertEqual(
            response.data["my_players"][0]["last_activity"],
            self.player.last_seen_at.isoformat().replace("+00:00", "Z"),
        )
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

        with patch(
            "accounts.views.coach_dashboard._dashboard_now",
            return_value=timezone.datetime(2026, 4, 8, 12, 0, tzinfo=dt_timezone.utc),
        ):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stats"]["sessions_this_week"], 2)

    def test_dashboard_excludes_sessions_earlier_today_from_upcoming(self):
        mocked_now = timezone.datetime(2026, 4, 8, 15, 0, tzinfo=dt_timezone.utc)
        mocked_today = mocked_now.date()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Upcoming Filter Plan",
            start_date=mocked_today,
            end_date=mocked_today + timedelta(days=7),
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        TrainingSession.objects.create(
            plan=plan,
            title="Past Today",
            session_date=mocked_today,
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Later Today",
            session_date=mocked_today,
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Tomorrow",
            session_date=mocked_today + timedelta(days=1),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        TrainingSession.objects.create(
            plan=plan,
            title="No Start Time",
            session_date=mocked_today,
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=None,
            end_time=None,
        )

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [session["title"] for session in response.data["upcoming_sessions"]],
            ["Later Today", "Tomorrow"],
        )
