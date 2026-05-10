from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import PlayerProfile, Position, Role, User, UserRole
from training.models import (
    PlayerCheckin,
    SessionAttendance,
    SessionLifecycle,
    TrainingPlan,
    TrainingPlanPlayer,
    TrainingSession,
    WeeklyLoad,
)
from training.statuses import Intensity, SleepQuality


URL = "/api/player/performance/"


def _make_player(email="performanceplayer@example.com", *, with_profile=True):
    player_role = Role.objects.get_or_create(role_name="Player")[0]
    user = User.objects.create_user(
        email=email,
        password="StrongPass123!",
        name="Performance Player",
    )
    UserRole.objects.create(user=user, role=player_role)
    if with_profile:
        position = Position.objects.get(code="ST")
        PlayerProfile.objects.create(user=user, position=position, login_status="COMPLETE")
    return user


def _make_coach(email="performancecoach@example.com"):
    coach_role = Role.objects.get_or_create(role_name="Coach")[0]
    user = User.objects.create_user(
        email=email,
        password="StrongPass123!",
        name="Performance Coach",
    )
    UserRole.objects.create(user=user, role=coach_role)
    return user


class PlayerPerformanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player = _make_player()
        self.client.force_authenticate(user=self.player)
        self.plan = TrainingPlan.objects.create(
            creator=self.player,
            title="Performance Plan",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            status="PUBLISHED",
        )
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player, assigned_by=self.player)

    def _session(self, day, title, *, completed=False, attended=False, intensity=Intensity.MEDIUM):
        session = TrainingSession.objects.create(
            plan=self.plan,
            title=title,
            session_date=day,
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            intensity=intensity,
        )
        if completed:
            SessionLifecycle.objects.create(session=session, status=SessionLifecycle.COMPLETED)
        if attended:
            SessionAttendance.objects.create(
                session=session,
                player=self.player,
                status=SessionAttendance.PRESENT,
            )
        return session

    def _get(self, start="2024-01-01", end="2024-01-03"):
        params = {}
        if start is not None:
            params["start_date"] = start
        if end is not None:
            params["end_date"] = end
        return self.client.get(URL, params)

    def test_response_contains_only_days(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data.keys()), {"days"})
        self.assertEqual(len(response.data["days"]), 3)
        self.assertNotIn("range", response.data)
        self.assertNotIn("selected_day", response.data)
        self.assertNotIn("metrics", response.data)
        self.assertNotIn("chart", response.data)
        self.assertNotIn("milestones", response.data)
        self.assertNotIn("score_breakdown", response.data)
        self.assertNotIn("data_quality", response.data)

    def test_daily_chart_calculates_sessions_effort_recovery_consistency_and_score(self):
        self._session(date(2024, 1, 1), "Completed", completed=True, attended=True)
        self._session(date(2024, 1, 2), "Missed", completed=True, attended=False)
        PlayerCheckin.objects.create(
            player=self.player,
            date=date(2024, 1, 1),
            sleep_hours="7.00",
            sleep_quality=SleepQuality.GOOD,
            mood=4,
            sore_zones=[],
            readiness_score=80,
        )
        PlayerCheckin.objects.create(
            player=self.player,
            date=date(2024, 1, 2),
            sleep_hours="6.00",
            sleep_quality=SleepQuality.FAIR,
            mood=3,
            sore_zones=["knee"],
            readiness_score=60,
        )

        response = self._get()

        self.assertEqual(response.status_code, 200)
        day1, day2, day3 = response.data["days"]
        self.assertEqual(day1["date"], "2024-01-01")
        self.assertEqual(day1["sessions"], {"completed": 1, "planned": 1, "percentage": 100})
        self.assertEqual(day1["effort"], {"percentage": 100, "source": "INTENSITY_WEIGHTED_SESSION_COMPLETION"})
        self.assertEqual(day1["recovery"], {"percentage": 80, "source": "PLAYER_CHECKINS"})
        self.assertEqual(day1["consistency"], {"percentage": 100, "streak_days": 1})
        self.assertEqual(day1["score"], 93)

        self.assertEqual(day2["sessions"], {"completed": 0, "planned": 1, "percentage": 0})
        self.assertEqual(day2["recovery"], {"percentage": 60, "source": "PLAYER_CHECKINS"})
        self.assertEqual(day2["consistency"], {"percentage": 0, "streak_days": 0})
        self.assertEqual(day2["score"], 21)

        self.assertEqual(day3["sessions"], {"completed": 0, "planned": 0, "percentage": 0})
        self.assertEqual(day3["recovery"], {"percentage": 0, "source": "PLAYER_CHECKINS"})
        self.assertEqual(day3["consistency"], {"percentage": 0, "streak_days": 0})
        self.assertEqual(day3["score"], 0)

    def test_recovery_uses_only_that_days_checkin(self):
        PlayerCheckin.objects.create(
            player=self.player,
            date=date(2024, 1, 1),
            sleep_hours="7.00",
            sleep_quality=SleepQuality.GOOD,
            mood=4,
            sore_zones=[],
            readiness_score=80,
        )
        PlayerCheckin.objects.create(
            player=self.player,
            date=date(2024, 1, 3),
            sleep_hours="5.00",
            sleep_quality=SleepQuality.POOR,
            mood=2,
            sore_zones=["hamstring"],
            readiness_score=35,
        )

        response = self._get("2024-01-01", "2024-01-03")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [day["recovery"]["percentage"] for day in response.data["days"]],
            [80, 0, 35],
        )

    def test_effort_weights_completed_sessions_by_intensity(self):
        self._session(
            date(2024, 1, 1),
            "Low completed",
            completed=True,
            attended=True,
            intensity=Intensity.LOW,
        )
        self._session(
            date(2024, 1, 1),
            "High missed",
            completed=True,
            attended=False,
            intensity=Intensity.HIGH,
        )
        PlayerCheckin.objects.create(
            player=self.player,
            date=date(2024, 1, 1),
            sleep_hours="7.00",
            sleep_quality=SleepQuality.GOOD,
            mood=4,
            sore_zones=[],
            readiness_score=80,
        )

        response = self._get("2024-01-01", "2024-01-01")

        self.assertEqual(response.status_code, 200)
        day = response.data["days"][0]
        self.assertEqual(day["sessions"], {"completed": 1, "planned": 2, "percentage": 50})
        self.assertEqual(day["effort"], {
            "percentage": 25,
            "source": "INTENSITY_WEIGHTED_SESSION_COMPLETION",
        })
        self.assertEqual(day["score"], 48)

    def test_completed_sessions_require_completed_lifecycle_and_player_attendance(self):
        lifecycle_only = self._session(date(2024, 1, 1), "Lifecycle only", completed=True)
        attendance_only = self._session(date(2024, 1, 1), "Attendance only")
        SessionAttendance.objects.create(
            session=attendance_only,
            player=self.player,
            status=SessionAttendance.PRESENT,
        )
        other_player = _make_player(email="otherperformance@example.com")
        SessionAttendance.objects.create(
            session=lifecycle_only,
            player=other_player,
            status=SessionAttendance.PRESENT,
        )

        response = self._get("2024-01-01", "2024-01-01")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["days"][0]["sessions"]["planned"], 2)
        self.assertEqual(response.data["days"][0]["sessions"]["completed"], 0)
        self.assertEqual(response.data["days"][0]["sessions"]["percentage"], 0)

    def test_sessions_for_unassigned_plans_are_excluded(self):
        other_player = _make_player(email="otherplanperformance@example.com")
        other_plan = TrainingPlan.objects.create(
            creator=other_player,
            title="Other Plan",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 3),
            status="PUBLISHED",
        )
        TrainingPlanPlayer.objects.create(plan=other_plan, player=other_player, assigned_by=other_player)
        TrainingSession.objects.create(
            plan=other_plan,
            title="Not Mine",
            session_date=date(2024, 1, 1),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )

        response = self._get("2024-01-01", "2024-01-01")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["days"][0]["sessions"]["planned"], 0)

    def test_recovery_is_zero_when_no_checkins_in_range(self):
        response = self._get("2024-01-01", "2024-01-01")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["days"][0]["recovery"]["percentage"], 0)
        self.assertEqual(response.data["days"][0]["score"], 0)

    def test_consistency_streak_is_daily_and_does_not_use_weekly_load(self):
        self._session(date(2024, 1, 1), "Completed one", completed=True, attended=True)
        self._session(date(2024, 1, 2), "Missed", completed=True, attended=False)
        self._session(date(2024, 1, 3), "Completed two", completed=True, attended=True)
        WeeklyLoad.objects.create(
            player=self.player,
            week_start=date(2024, 1, 1),
            streak_days=7,
        )

        response = self._get("2024-01-01", "2024-01-03")

        self.assertEqual(response.status_code, 200)
        day1, day2, day3 = response.data["days"]
        self.assertEqual(day1["consistency"], {"percentage": 100, "streak_days": 1})
        self.assertEqual(day2["consistency"], {"percentage": 0, "streak_days": 0})
        self.assertEqual(day3["consistency"], {"percentage": 100, "streak_days": 1})

    def test_missing_start_date_returns_400(self):
        response = self._get(start=None, end="2024-01-03")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "start_date is required.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_missing_end_date_returns_400(self):
        response = self._get(start="2024-01-01", end=None)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "end_date is required.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_invalid_date_and_range_validation(self):
        invalid = self._get(start="01-01-2024", end="2024-01-03")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.data["detail"], "Invalid start_date format.")

        reversed_range = self._get(start="2024-01-03", end="2024-01-01")
        self.assertEqual(reversed_range.status_code, 400)
        self.assertEqual(reversed_range.data["detail"], "start_date must be less than or equal to end_date.")

        too_long = self._get(start="2024-01-01", end="2024-02-01")
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(too_long.data["detail"], "Date range must not exceed 31 days.")

    def test_auth_and_player_permission(self):
        unauthenticated = APIClient()
        response = unauthenticated.get(URL, {"start_date": "2024-01-01", "end_date": "2024-01-01"})
        self.assertEqual(response.status_code, 401)

        coach_client = APIClient()
        coach_client.force_authenticate(user=_make_coach())
        response = coach_client.get(URL, {"start_date": "2024-01-01", "end_date": "2024-01-01"})
        self.assertEqual(response.status_code, 403)
