from datetime import date, time

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
from training.statuses import Intensity


URL = "/api/player/training/"


def make_player(email="rangeplayer@example.com"):
    player_role = Role.objects.get_or_create(role_name="Player")[0]
    user = User.objects.create_user(
        email=email,
        password="StrongPass123!",
        name="Range Player",
    )
    UserRole.objects.create(user=user, role=player_role)
    striker = Position.objects.get(code="ST")
    PlayerProfile.objects.create(user=user, position=striker, login_status="complete")
    return user


class PlayerTrainingRangeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player = make_player()
        self.plan = TrainingPlan.objects.create(
            creator=self.player,
            title="Speed Plan",
            start_date="2026-04-01",
            end_date="2026-04-07",
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player, assigned_by=self.player)

        self.s1 = TrainingSession.objects.create(
            plan=self.plan,
            title="Warm-up",
            session_date=date(2026, 4, 1),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(10, 30),
            intensity=Intensity.MEDIUM,
            location="Main Field",
            squad_size=20,
            notes="Bring water",
            coach_note="Keep pace moderate",
        )
        self.s2 = TrainingSession.objects.create(
            plan=self.plan,
            title="Sprint Drill",
            session_date=date(2026, 4, 1),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(11, 0),
            end_time=time(12, 0),
        )
        self.s3 = TrainingSession.objects.create(
            plan=self.plan,
            title="Recovery",
            session_date=date(2026, 4, 3),
            session_type=TrainingSession.SESSION_TYPE_TEAM,
            start_time=time(9, 0),
            end_time=time(9, 45),
        )
        SessionLifecycle.objects.create(session=self.s1, status=SessionLifecycle.COMPLETED)
        SessionAttendance.objects.create(
            session=self.s1, player=self.player, status=SessionAttendance.PRESENT,
        )

        self.client.force_authenticate(user=self.player)

    def _dates(self, response):
        return [day["date"] for day in response.data["days"]]

    def test_range_returns_sparse_list_of_days_sorted_asc(self):
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-07"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["start_date"], "2026-04-01")
        self.assertEqual(response.data["end_date"], "2026-04-07")
        self.assertEqual(self._dates(response), ["2026-04-01", "2026-04-03"])

    def test_sessions_within_a_day_grouped_by_plan_with_all_fields(self):
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-01"})

        day = response.data["days"][0]
        self.assertEqual(day["date"], "2026-04-01")
        self.assertEqual(len(day["plans"]), 1)

        plan = day["plans"][0]
        self.assertEqual(plan["plan_id"], str(self.plan.plan_id))
        self.assertEqual(plan["title"], "Speed Plan")
        self.assertEqual(len(plan["sessions"]), 2)

        first = plan["sessions"][0]
        self.assertEqual(first["session_id"], str(self.s1.session_id))
        self.assertEqual(first["title"], "Warm-up")
        self.assertEqual(first["session_type"], "GROUP")
        self.assertEqual(first["session_date"], "2026-04-01")
        self.assertEqual(first["start_time"], "10:00:00")
        self.assertEqual(first["end_time"], "10:30:00")
        self.assertEqual(first["intensity"], "MEDIUM")
        self.assertEqual(first["location"], "Main Field")
        self.assertEqual(first["squad_size"], 20)
        self.assertNotIn("notes", first)
        self.assertNotIn("duration_minutes", first)
        self.assertEqual(first["coach_note"], "Keep pace moderate")
        self.assertEqual(first["status"], "COMPLETED")

    def test_sessions_are_ordered_by_start_time(self):
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-01"})
        titles = [s["title"] for s in response.data["days"][0]["plans"][0]["sessions"]]
        self.assertEqual(titles, ["Warm-up", "Sprint Drill"])

    def test_completed_session_without_attendance_is_missed(self):
        SessionLifecycle.objects.create(session=self.s2, status=SessionLifecycle.COMPLETED)
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-01"})
        sessions = response.data["days"][0]["plans"][0]["sessions"]
        sprint = next(s for s in sessions if s["session_id"] == str(self.s2.session_id))
        self.assertEqual(sprint["status"], "MISSED")

    def test_in_progress_session_returns_in_progress_status(self):
        SessionLifecycle.objects.create(session=self.s2, status=SessionLifecycle.IN_PROGRESS)
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-01"})
        sessions = response.data["days"][0]["plans"][0]["sessions"]
        sprint = next(s for s in sessions if s["session_id"] == str(self.s2.session_id))
        self.assertEqual(sprint["status"], "IN_PROGRESS")

    def test_session_without_lifecycle_is_not_started(self):
        response = self.client.get(URL, {"start_date": "2026-04-03", "end_date": "2026-04-03"})
        sessions = response.data["days"][0]["plans"][0]["sessions"]
        self.assertEqual(sessions[0]["status"], "NOT_STARTED")

    def test_default_is_today_single_day(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["start_date"], date.today().isoformat())
        self.assertEqual(response.data["end_date"], date.today().isoformat())

    def test_days_without_sessions_are_omitted(self):
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-07"})
        self.assertNotIn("2026-04-02", self._dates(response))
        self.assertNotIn("2026-04-04", self._dates(response))

    def test_sessions_outside_the_range_do_not_leak(self):
        TrainingSession.objects.create(
            plan=self.plan,
            title="Outside",
            session_date=date(2026, 4, 10),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-07"})
        self.assertNotIn("2026-04-10", self._dates(response))

    def test_sessions_from_unassigned_plans_are_ignored(self):
        other = make_player(email="other@example.com")
        other_plan = TrainingPlan.objects.create(
            creator=other,
            title="Other Plan",
            start_date="2026-04-01",
            end_date="2026-04-02",
            status="draft",
        )
        TrainingPlanPlayer.objects.create(plan=other_plan, player=other, assigned_by=other)
        TrainingSession.objects.create(
            plan=other_plan,
            title="Not mine",
            session_date=date(2026, 4, 2),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        response = self.client.get(URL, {"start_date": "2026-04-02", "end_date": "2026-04-02"})
        self.assertEqual(self._dates(response), [])

    def test_invalid_start_date_returns_400_with_expected(self):
        response = self.client.get(URL, {"start_date": "bad", "end_date": "2026-04-02"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid start_date format.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_invalid_end_date_returns_400_with_expected(self):
        response = self.client.get(URL, {"start_date": "2026-04-02", "end_date": "nope"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid end_date format.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_start_after_end_returns_400(self):
        response = self.client.get(URL, {"start_date": "2026-04-05", "end_date": "2026-04-02"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "start_date must be less than or equal to end_date.")

    def test_range_longer_than_31_days_returns_400(self):
        response = self.client.get(URL, {"start_date": "2026-01-01", "end_date": "2026-02-15"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Date range must not exceed 31 days.")

    def test_exactly_31_days_is_allowed(self):
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-05-01"})
        self.assertEqual(response.status_code, 200)

    def test_single_day_with_equal_start_and_end_is_allowed(self):
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-01"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._dates(response), ["2026-04-01"])

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(URL, {"start_date": "2026-04-01", "end_date": "2026-04-02"})
        self.assertEqual(response.status_code, 401)

    def test_old_day_endpoint_is_gone(self):
        response = self.client.get("/api/player/training/day/")
        self.assertEqual(response.status_code, 404)
