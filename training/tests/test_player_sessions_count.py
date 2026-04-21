from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import PlayerProfile, Position, Role, User, UserRole
from training.models import (
    SessionAttendance,
    SessionLifecycle,
    TrainingPlan,
    TrainingPlanPlayer,
    TrainingSession,
)


URL = "/api/player/sessions/count/"


def _make_player(email="countsplayer@example.com", *, with_profile=True):
    player_role = Role.objects.get_or_create(role_name="Player")[0]
    user = User.objects.create_user(
        email=email,
        password="StrongPass123!",
        name="Counts Player",
    )
    UserRole.objects.create(user=user, role=player_role)
    if with_profile:
        striker = Position.objects.get(code="ST")
        PlayerProfile.objects.create(user=user, position=striker, login_status="COMPLETE")
    return user


def _make_coach(email="countscoach@example.com"):
    coach_role = Role.objects.get_or_create(role_name="Coach")[0]
    user = User.objects.create_user(
        email=email,
        password="StrongPass123!",
        name="Counts Coach",
    )
    UserRole.objects.create(user=user, role=coach_role)
    return user


class PlayerSessionsCountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player = _make_player()
        self.plan = TrainingPlan.objects.create(
            creator=self.player,
            title="Speed Plan",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            status="DRAFT",
        )
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player, assigned_by=self.player)

        # Day 1: completed+attended, completed+missed, in_progress, not_started
        self.s_day1_completed_attended = self._mk_session(date(2024, 1, 1), "Warm-up")
        self.s_day1_completed_missed = self._mk_session(date(2024, 1, 1), "Sprint")
        self.s_day1_in_progress = self._mk_session(date(2024, 1, 1), "Drill")
        self.s_day1_not_started = self._mk_session(date(2024, 1, 1), "Cooldown")

        SessionLifecycle.objects.create(
            session=self.s_day1_completed_attended, status=SessionLifecycle.COMPLETED,
        )
        SessionAttendance.objects.create(
            session=self.s_day1_completed_attended,
            player=self.player,
            status=SessionAttendance.PRESENT,
        )

        SessionLifecycle.objects.create(
            session=self.s_day1_completed_missed, status=SessionLifecycle.COMPLETED,
        )

        SessionLifecycle.objects.create(
            session=self.s_day1_in_progress, status=SessionLifecycle.IN_PROGRESS,
        )

        # Day 3: a session with no lifecycle row at all -> not_started
        self.s_day3 = self._mk_session(date(2024, 1, 3), "Recovery")

        self.client.force_authenticate(user=self.player)

    def _mk_session(self, day, title):
        return TrainingSession.objects.create(
            plan=self.plan,
            title=title,
            session_date=day,
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )

    def _get(self, start="2024-01-01", end="2024-01-31"):
        params = {}
        if start is not None:
            params["start_date"] = start
        if end is not None:
            params["end_date"] = end
        return self.client.get(URL, params)

    def _day(self, response, date_str):
        for item in response.data["days"]:
            if item["date"] == date_str:
                return item
        raise AssertionError(f"date {date_str} not in response days")

    # ----- envelope and bucketing -----

    def test_envelope_fields(self):
        response = self._get("2024-01-01", "2024-01-31")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["start_date"], "2024-01-01")
        self.assertEqual(response.data["end_date"], "2024-01-31")
        self.assertNotIn("month", response.data)
        self.assertEqual(len(response.data["days"]), 31)

    def test_day_with_all_buckets_counts_correctly(self):
        response = self._get()
        day1 = self._day(response, "2024-01-01")
        self.assertEqual(day1["completed_count"], 1)
        self.assertEqual(day1["missed_count"], 1)
        self.assertEqual(day1["in_progress_count"], 1)
        self.assertEqual(day1["not_started_count"], 1)

    def test_session_without_lifecycle_counts_as_not_started(self):
        response = self._get()
        day3 = self._day(response, "2024-01-03")
        self.assertEqual(day3["completed_count"], 0)
        self.assertEqual(day3["missed_count"], 0)
        self.assertEqual(day3["in_progress_count"], 0)
        self.assertEqual(day3["not_started_count"], 1)

    def test_day_without_sessions_is_zero_filled(self):
        response = self._get()
        day2 = self._day(response, "2024-01-02")
        for k in ("completed_count", "missed_count", "in_progress_count", "not_started_count"):
            self.assertEqual(day2[k], 0)

    def test_sessions_outside_range_are_excluded(self):
        TrainingSession.objects.create(
            plan=self.plan,
            title="February",
            session_date=date(2024, 2, 15),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )
        response = self._get("2024-01-01", "2024-01-31")
        total = sum(
            d["completed_count"] + d["missed_count"]
            + d["in_progress_count"] + d["not_started_count"]
            for d in response.data["days"]
        )
        self.assertEqual(total, 5)

    def test_sessions_for_unassigned_plans_are_excluded(self):
        other_player = _make_player(email="other@example.com")
        other_plan = TrainingPlan.objects.create(
            creator=other_player,
            title="Other Plan",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            status="DRAFT",
        )
        TrainingPlanPlayer.objects.create(plan=other_plan, player=other_player, assigned_by=other_player)
        TrainingSession.objects.create(
            plan=other_plan,
            title="Not Mine",
            session_date=date(2024, 1, 5),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )
        response = self._get()
        day5 = self._day(response, "2024-01-05")
        for k in ("completed_count", "missed_count", "in_progress_count", "not_started_count"):
            self.assertEqual(day5[k], 0)

    def test_attendance_for_other_player_does_not_count_for_me(self):
        teammate = _make_player(email="teammate@example.com")
        TrainingPlanPlayer.objects.create(plan=self.plan, player=teammate, assigned_by=self.player)
        SessionAttendance.objects.create(
            session=self.s_day1_completed_missed,
            player=teammate,
            status=SessionAttendance.PRESENT,
        )
        response = self._get()
        day1 = self._day(response, "2024-01-01")
        self.assertEqual(day1["completed_count"], 1)
        self.assertEqual(day1["missed_count"], 1)

    def test_player_with_no_plans_returns_zeros(self):
        empty_player = _make_player(email="empty@example.com")
        self.client.force_authenticate(user=empty_player)
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["days"]), 31)
        for item in response.data["days"]:
            for k in ("completed_count", "missed_count", "in_progress_count", "not_started_count"):
                self.assertEqual(item[k], 0)

    def test_single_day_range(self):
        response = self._get("2024-01-01", "2024-01-01")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["days"]), 1)
        self.assertEqual(response.data["days"][0]["date"], "2024-01-01")

    def test_31_day_range_is_accepted(self):
        response = self._get("2024-01-01", "2024-01-31")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["days"]), 31)

    # ----- validation -----

    def test_missing_start_date_returns_400(self):
        response = self.client.get(URL, {"end_date": "2024-01-31"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "start_date is required.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_missing_end_date_returns_400(self):
        response = self.client.get(URL, {"start_date": "2024-01-01"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "end_date is required.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_invalid_start_date_format_returns_400(self):
        response = self.client.get(URL, {"start_date": "01-01-2024", "end_date": "2024-01-31"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid start_date format.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_invalid_end_date_format_returns_400(self):
        response = self.client.get(URL, {"start_date": "2024-01-01", "end_date": "31/01/2024"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid end_date format.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_start_after_end_returns_400(self):
        response = self._get("2024-01-15", "2024-01-10")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "start_date must be less than or equal to end_date.",
        )
        self.assertNotIn("expected", response.data)

    def test_range_over_31_days_returns_400(self):
        response = self._get("2024-01-01", "2024-02-01")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Date range must not exceed 31 days.")

    # ----- auth -----

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(URL, {"start_date": "2024-01-01", "end_date": "2024-01-31"})
        self.assertEqual(response.status_code, 401)

    def test_non_player_returns_403(self):
        coach = _make_coach()
        client = APIClient()
        client.force_authenticate(user=coach)
        response = client.get(URL, {"start_date": "2024-01-01", "end_date": "2024-01-31"})
        self.assertEqual(response.status_code, 403)
