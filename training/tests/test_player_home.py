from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import PlayerProfile, Position, Role, User, UserRole
from training.models import AIInsight, PlayerCheckin, TrainingPlan, TrainingPlanPlayer, TrainingSession, WeeklyLoad
from training.services.player_home import (
    _compute_distance_delta_pct,
    _compute_load_ratio,
    get_load_status,
    get_readiness_label,
)
from training.statuses import InsightTag, SleepQuality

HOME_URL = "/api/player/home/"


def make_player(email="homeplayer@example.com"):
    role = Role.objects.get_or_create(role_name="Player")[0]
    user = User.objects.create_user(email=email, password="StrongPass123!", name="Home Player")
    UserRole.objects.create(user=user, role=role)
    position = Position.objects.get(code="ST")
    PlayerProfile.objects.create(user=user, position=position, login_status="complete")
    return user


def make_plan_with_session(player, session_date, start_time=None, **session_kwargs):
    plan = TrainingPlan.objects.create(
        creator=player,
        title="Test Plan",
        start_date=session_date,
        end_date=session_date + timedelta(days=7),
        status="published",
    )
    TrainingPlanPlayer.objects.create(plan=plan, player=player, assigned_by=player)
    session = TrainingSession.objects.create(
        plan=plan,
        title=session_kwargs.pop("title", "Session"),
        session_date=session_date,
        start_time=start_time,
        **session_kwargs,
    )
    return plan, session


# ─────────────────────────────────────────────
# Pure unit tests — no DB
# ─────────────────────────────────────────────

class PlayerHomeServiceTests(TestCase):

    def test_readiness_label_bands(self):
        self.assertEqual(get_readiness_label(100), "Ready to perform")
        self.assertEqual(get_readiness_label(80),  "Ready to perform")
        self.assertEqual(get_readiness_label(79),  "Good to train")
        self.assertEqual(get_readiness_label(60),  "Good to train")
        self.assertEqual(get_readiness_label(59),  "Train with caution")
        self.assertEqual(get_readiness_label(40),  "Train with caution")
        self.assertEqual(get_readiness_label(39),  "Consider rest today")
        self.assertEqual(get_readiness_label(0),   "Consider rest today")

    def test_load_status_bands(self):
        self.assertEqual(get_load_status(0.8),  "safe")
        self.assertEqual(get_load_status(1.29), "safe")
        self.assertEqual(get_load_status(1.3),  "caution")
        self.assertEqual(get_load_status(1.49), "caution")
        self.assertEqual(get_load_status(1.5),  "danger")
        self.assertEqual(get_load_status(2.0),  "danger")

    def test_distance_delta_pct_rounds_correctly(self):
        self.assertEqual(_compute_distance_delta_pct(47.3, 42.1), 12)
        self.assertEqual(_compute_distance_delta_pct(50.0, 40.0), 25)

    def test_distance_delta_pct_none_when_no_prev_week(self):
        self.assertIsNone(_compute_distance_delta_pct(47.3, None))
        self.assertIsNone(_compute_distance_delta_pct(47.3, 0))

    def test_load_ratio_none_when_chronic_zero(self):
        self.assertIsNone(_compute_load_ratio(1840, 0))
        self.assertIsNone(_compute_load_ratio(1840, None))
        self.assertEqual(_compute_load_ratio(1840, 1620), 1.14)


# ─────────────────────────────────────────────
# Endpoint integration tests
# ─────────────────────────────────────────────

class PlayerHomeEndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.player = make_player()
        self.client.force_authenticate(user=self.player)
        self.today = date.today()

    def test_returns_200_for_authenticated_player(self):
        response = self.client.get(HOME_URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn("readiness", response.data)
        self.assertIn("upcoming_sessions", response.data)
        self.assertIn("weekly_progress", response.data)
        self.assertIn("ai_insights", response.data)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        self.assertEqual(self.client.get(HOME_URL).status_code, 401)

    def test_readiness_null_when_no_checkin_today(self):
        response = self.client.get(HOME_URL)
        readiness = response.data["readiness"]
        self.assertFalse(readiness["submitted_today"])
        self.assertIsNone(readiness["score"])
        self.assertIsNone(readiness["label"])
        self.assertEqual(readiness["sore_zones"], [])

    def test_readiness_populated_when_checkin_exists(self):
        PlayerCheckin.objects.create(
            player=self.player,
            date=self.today,
            sleep_hours="7.00",
            sleep_quality=SleepQuality.GOOD,
            mood=4,
            sore_zones=["knee"],
            readiness_score=82,
        )
        response = self.client.get(HOME_URL)
        readiness = response.data["readiness"]
        self.assertTrue(readiness["submitted_today"])
        self.assertEqual(readiness["score"], 82)
        self.assertEqual(readiness["label"], "Ready to perform")
        self.assertEqual(readiness["mood"], 4)
        self.assertEqual(readiness["sore_zones"], ["knee"])

    def test_upcoming_sessions_ordered_by_date_then_time(self):
        tomorrow = self.today + timedelta(days=1)
        day_after = self.today + timedelta(days=2)
        make_plan_with_session(self.player, day_after,  start_time="09:00", title="Later")
        make_plan_with_session(self.player, tomorrow,   start_time="18:00", title="First")
        response = self.client.get(HOME_URL)
        sessions = response.data["upcoming_sessions"]
        self.assertGreaterEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["title"], "First")
        self.assertEqual(sessions[1]["title"], "Later")

    def test_upcoming_sessions_do_not_include_is_today(self):
        make_plan_with_session(self.player, self.today, start_time="10:00", title="Today's session")
        future = self.today + timedelta(days=3)
        make_plan_with_session(self.player, future, start_time="10:00", title="Future session")
        response = self.client.get(HOME_URL)
        for session in response.data["upcoming_sessions"]:
            self.assertNotIn("is_today", session)

    def test_weekly_progress_delta_computed_correctly(self):
        week_start      = self.today - timedelta(days=self.today.weekday())
        prev_week_start = week_start - timedelta(weeks=1)
        WeeklyLoad.objects.create(
            player=self.player, week_start=week_start,
            distance_km="50.00", acute_load=1800, chronic_load=1500,
            sessions_completed=4, sessions_planned=5,
        )
        WeeklyLoad.objects.create(
            player=self.player, week_start=prev_week_start,
            distance_km="40.00", acute_load=1500, chronic_load=1500,
            sessions_completed=5, sessions_planned=5,
        )
        response = self.client.get(HOME_URL)
        wp = response.data["weekly_progress"]
        self.assertEqual(wp["distance_km"], 50.0)
        self.assertEqual(wp["distance_km_prev"], 40.0)
        self.assertEqual(wp["distance_delta_pct"], 25)
        self.assertEqual(wp["load_ratio"], 1.2)
        self.assertEqual(wp["load_status"], "safe")

    def test_empty_ai_insights_returns_empty_list(self):
        response = self.client.get(HOME_URL)
        self.assertEqual(response.data["ai_insights"], [])

    def test_ai_insights_returned_when_present(self):
        AIInsight.objects.create(
            player=self.player,
            date=self.today,
            tag=InsightTag.LOAD,
            text="You've covered 12% more distance this week.",
        )
        response = self.client.get(HOME_URL)
        insights = response.data["ai_insights"]
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]["tag"], "load")
