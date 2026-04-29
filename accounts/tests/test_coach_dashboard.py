from datetime import time, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import (
    SessionAttendance,
    SessionLifecycle,
    TrainingPlan,
    TrainingPlanPlayer,
    TrainingSession,
)


def _make_player(email, coach, position, state="ACTIVE"):
    player = User.objects.create_user(email=email, password="Pass123!", name=email.split("@")[0])
    player_role = Role.objects.get(role_name="Player")
    UserRole.objects.create(user=player, role=player_role)
    PlayerProfile.objects.create(user=player, coach=coach, position=position, state=state)
    return player


def _make_plan(coach, title="Plan", *, today):
    return TrainingPlan.objects.create(
        creator=coach,
        title=title,
        start_date=today,
        end_date=today + timedelta(days=30),
        status="DRAFT",
    )


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

        self.position = Position.objects.get(code="CM")

        self.player = User.objects.create_user(
            email="dashplayer@example.com",
            password="StrongPass123!",
            name="Dash Player",
        )
        UserRole.objects.create(user=self.player, role=self.player_role)
        PlayerProfile.objects.create(
            user=self.player,
            coach=self.coach,
            position=self.position,
        )

        self.client.force_authenticate(user=self.coach)

    # ------------------------------------------------------------------
    # Test 1 — overview_stats.total_players
    # ------------------------------------------------------------------
    def test_overview_stats_total_players(self):
        mocked_now = timezone.datetime(2026, 4, 20, 8, 0, tzinfo=dt_timezone.utc)
        today = mocked_now.date()

        # second ACTIVE player created this month
        p2 = _make_player("p2@example.com", self.coach, self.position, state="ACTIVE")
        # injured player (counts toward total_all, not active)
        _make_player("p3@example.com", self.coach, self.position, state="INJURED")

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        stats = response.data["overview_stats"]["total_players"]
        # setUp player + p2 are ACTIVE
        self.assertEqual(stats["value"], 2)
        # delta_value = ACTIVE players created this month; both were just created
        self.assertGreaterEqual(stats["delta_value"], 1)

    # ------------------------------------------------------------------
    # Test 2 — overview_stats.sessions_today
    # ------------------------------------------------------------------
    def test_overview_stats_sessions_today(self):
        mocked_now = timezone.datetime(2026, 4, 8, 8, 0, tzinfo=dt_timezone.utc)
        today = mocked_now.date()

        plan = _make_plan(self.coach, today=today)
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        # session 1 — completed (lifecycle with ended_at), start_time before now
        s1 = TrainingSession.objects.create(
            plan=plan, title="S1", session_date=today,
            session_type="GROUP", start_time=time(7, 0), end_time=time(8, 0),
        )
        lc1 = SessionLifecycle.objects.create(session=s1, status="COMPLETED")
        lc1.ended_at = mocked_now - timedelta(minutes=30)
        lc1.save(update_fields=["ended_at"])

        # session 2 — upcoming today (09:00), not completed
        s2 = TrainingSession.objects.create(
            plan=plan, title="S2", session_date=today,
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 0),
        )

        # session 3 — tomorrow (should not count in sessions_today)
        TrainingSession.objects.create(
            plan=plan, title="S3", session_date=today + timedelta(days=1),
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 0),
        )

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        today_stats = response.data["overview_stats"]["sessions_today"]
        self.assertEqual(today_stats["value"], 2)
        self.assertEqual(today_stats["completed_count"], 1)
        self.assertEqual(today_stats["next_start_time"], "09:00")

    # ------------------------------------------------------------------
    # Test 3 — overview_stats.attendance_week math
    # ------------------------------------------------------------------
    def test_attendance_week_math(self):
        # Mock now = Wednesday 2026-04-08; week_start = Sunday 2026-04-05
        mocked_now = timezone.datetime(2026, 4, 8, 12, 0, tzinfo=dt_timezone.utc)
        today = mocked_now.date()
        week_start = today - timedelta(days=(today.weekday() + 1) % 7)  # 2026-04-05
        last_week_start = week_start - timedelta(days=7)                # 2026-03-29

        plan = _make_plan(self.coach, today=last_week_start)
        p2 = _make_player("att2@example.com", self.coach, self.position)
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        TrainingPlanPlayer.objects.create(plan=plan, player=p2, assigned_by=self.coach)
        # expected per session = 2 players

        # This week: 1 session, both attend → 100%
        s_this = TrainingSession.objects.create(
            plan=plan, title="ThisWeek", session_date=week_start,
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 0),
        )
        lc_this = SessionLifecycle.objects.create(session=s_this, status="COMPLETED")
        lc_this.ended_at = timezone.datetime(2026, 4, 5, 10, 0, tzinfo=dt_timezone.utc)
        lc_this.save(update_fields=["ended_at"])
        SessionAttendance.objects.create(session=s_this, player=self.player, status="PRESENT", marked_by=self.coach)
        SessionAttendance.objects.create(session=s_this, player=p2, status="PRESENT", marked_by=self.coach)

        # Last week: 1 session, only 1 of 2 attend → 50%
        s_last = TrainingSession.objects.create(
            plan=plan, title="LastWeek", session_date=last_week_start,
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 0),
        )
        lc_last = SessionLifecycle.objects.create(session=s_last, status="COMPLETED")
        lc_last.ended_at = timezone.datetime(2026, 3, 29, 10, 0, tzinfo=dt_timezone.utc)
        lc_last.save(update_fields=["ended_at"])
        SessionAttendance.objects.create(session=s_last, player=self.player, status="PRESENT", marked_by=self.coach)

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        att = response.data["overview_stats"]["attendance_week"]
        self.assertEqual(att["value_percent"], 100)   # 2/2 this week
        self.assertEqual(att["delta_percent"], 50)    # 100 - 50

    # ------------------------------------------------------------------
    # Test 4 — upcoming_sessions 48h window + status_label
    # ------------------------------------------------------------------
    def test_upcoming_sessions_48h_end_time_and_assigned_players(self):
        mocked_now = timezone.datetime(2026, 4, 8, 8, 0, tzinfo=dt_timezone.utc)
        today = mocked_now.date()

        plan = _make_plan(self.coach, today=today)
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        # session today
        TrainingSession.objects.create(
            plan=plan, title="Today Session", session_date=today,
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 30),
        )
        # session tomorrow
        TrainingSession.objects.create(
            plan=plan, title="Tomorrow Session", session_date=today + timedelta(days=1),
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 0),
        )
        # Beyond 48h — excluded
        TrainingSession.objects.create(
            plan=plan, title="Beyond Window", session_date=today + timedelta(days=3),
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 0),
        )

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        sessions = response.data["upcoming_sessions"]
        self.assertEqual(len(sessions), 2)

        first = sessions[0]
        self.assertEqual(first["title"], "Today Session")
        self.assertEqual(first["end_time"], "10:30:00")
        self.assertEqual(first["status"], "NOT_STARTED")
        self.assertEqual(len(first["assigned_players"]), 1)
        self.assertEqual(str(first["assigned_players"][0]["id"]), str(self.player.id))

        # old fields must not appear
        self.assertNotIn("status_label", first)
        self.assertNotIn("is_today", first)
        self.assertNotIn("duration_minutes", first)

    # ------------------------------------------------------------------
    # Test 5 - upcoming_sessions include available time windows and exclude completed lifecycle sessions
    # ------------------------------------------------------------------
    def test_upcoming_sessions_exclude_completed_sessions(self):
        mocked_now = timezone.datetime(2026, 4, 8, 8, 0, tzinfo=dt_timezone.utc)
        today = mocked_now.date()

        plan = _make_plan(self.coach, today=today)
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        completed_session = TrainingSession.objects.create(
            plan=plan,
            title="Completed Future Session",
            session_date=today,
            session_type="GROUP",
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        SessionLifecycle.objects.create(session=completed_session, status=SessionLifecycle.COMPLETED)

        active_session = TrainingSession.objects.create(
            plan=plan,
            title="Active Available Session",
            session_date=today,
            session_type="GROUP",
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        SessionLifecycle.objects.create(session=active_session, status=SessionLifecycle.IN_PROGRESS)

        expired_not_started_session = TrainingSession.objects.create(
            plan=plan,
            title="Expired Not Started Session",
            session_date=today,
            session_type="GROUP",
            start_time=time(6, 0),
            end_time=time(7, 0),
        )
        SessionLifecycle.objects.create(session=expired_not_started_session, status=SessionLifecycle.NOT_STARTED)

        in_progress_session = TrainingSession.objects.create(
            plan=plan,
            title="In Progress Without End Time",
            session_date=today,
            session_type="GROUP",
            start_time=time(7, 30),
            end_time=None,
        )
        SessionLifecycle.objects.create(session=in_progress_session, status=SessionLifecycle.IN_PROGRESS)

        TrainingSession.objects.create(
            plan=plan,
            title="Available Not Started Session",
            session_date=today + timedelta(days=1),
            session_type="GROUP",
            start_time=time(9, 0),
            end_time=time(10, 0),
        )

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        titles = [session["title"] for session in response.data["upcoming_sessions"]]
        self.assertNotIn("Completed Future Session", titles)
        self.assertNotIn("Expired Not Started Session", titles)
        self.assertEqual(titles, [
            "Active Available Session",
            "In Progress Without End Time",
            "Available Not Started Session",
        ])

    # ------------------------------------------------------------------
    # Test 6 - alerts: one per severity, correct order, alerts_total
    # ------------------------------------------------------------------
    def test_alerts_one_per_severity(self):
        mocked_now = timezone.datetime(2026, 4, 8, 8, 0, tzinfo=dt_timezone.utc)
        today = mocked_now.date()

        # CRITICAL — mark setUp player as INJURED
        profile = PlayerProfile.objects.get(user=self.player)
        profile.state = "INJURED"
        profile.save(update_fields=["state"])

        plan = _make_plan(self.coach, today=today - timedelta(days=10))
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        # WARNING — completed session with 0 attendance (0/1 < 70%)
        session = TrainingSession.objects.create(
            plan=plan, title="Low Attend", session_date=today - timedelta(days=1),
            session_type="GROUP", start_time=time(9, 0), end_time=time(10, 0),
        )
        lc = SessionLifecycle.objects.create(session=session, status="COMPLETED")
        lc.ended_at = timezone.datetime(2026, 4, 7, 10, 0, tzinfo=dt_timezone.utc)
        lc.save(update_fields=["ended_at"])
        # No attendance records → 0/1 = 0% < 70%

        # INFO — a *different* player assigned within 24h by someone other than the coach
        other_user = User.objects.create_user(
            email="other@example.com", password="Pass123!", name="Other"
        )
        info_player = _make_player("info_player@example.com", self.coach, self.position)
        tpp = TrainingPlanPlayer.objects.create(plan=plan, player=info_player, assigned_by=other_user)
        TrainingPlanPlayer.objects.filter(pk=tpp.pk).update(
            assigned_at=timezone.datetime(2026, 4, 8, 6, 0, tzinfo=dt_timezone.utc)
        )

        with patch("accounts.views.coach_dashboard._dashboard_now", return_value=mocked_now):
            response = self.client.get("/api/coach/dashboard/")

        self.assertEqual(response.status_code, 200)
        alerts = response.data["alerts"]
        self.assertGreaterEqual(response.data["alerts_total"], 3)

        severities = [a["severity"] for a in alerts]
        self.assertIn("CRITICAL", severities)
        self.assertIn("WARNING", severities)
        self.assertIn("INFO", severities)

        # order must be CRITICAL → WARNING → INFO
        order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        self.assertEqual(severities, sorted(severities, key=lambda s: order[s]))

        # old keys must not appear
        self.assertNotIn("stats", response.data)
        self.assertNotIn("my_players", response.data)
