from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import SessionLifecycle, TrainingPlan, TrainingPlanPlayer, TrainingSession


class CoachTrainingPlanValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        coach_role = Role.objects.create(role_name="Coach")
        player_role = Role.objects.create(role_name="Player")

        self.coach = User.objects.create_user(
            email="coachplan@example.com",
            password="StrongPass123!",
            name="Coach Plan",
        )
        UserRole.objects.create(user=self.coach, role=coach_role)
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")
        self.right_winger = Position.objects.get(code="RW")
        self.center_back = Position.objects.get(code="CB")

        self.player = User.objects.create_user(
            email="ownedplayer@example.com",
            password="StrongPass123!",
            name="Owned Player",
        )
        UserRole.objects.create(user=self.player, role=player_role)
        PlayerProfile.objects.create(
            user=self.player,
            coach=self.coach,
            position=self.right_winger,
        )

        other_coach = User.objects.create_user(
            email="othercoach@example.com",
            password="StrongPass123!",
            name="Other Coach",
        )
        UserRole.objects.create(user=other_coach, role=coach_role)
        CoachProfile.objects.create(user=other_coach, approval_status="APPROVED")

        self.other_player = User.objects.create_user(
            email="otherplayer@example.com",
            password="StrongPass123!",
            name="Other Player",
        )
        UserRole.objects.create(user=self.other_player, role=player_role)
        PlayerProfile.objects.create(
            user=self.other_player,
            coach=other_coach,
            position=self.center_back,
        )

        self.client.force_authenticate(user=self.coach)

    def test_list_returns_range_payload_grouped_by_day_and_plan(self):
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Season Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="DRAFT",
        )
        session = TrainingSession.objects.create(
            plan=plan,
            title="Session One",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(11, 0),
            location="Main Field",
            squad_size=18,
            coach_note="High tempo",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        SessionLifecycle.objects.create(session=session, status=SessionLifecycle.COMPLETED)

        response = self.client.get("/api/coach/plans/", {"start_date": "2026-04-01", "end_date": "2026-04-07"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["start_date"], "2026-04-01")
        self.assertEqual(response.data["end_date"], "2026-04-07")
        self.assertEqual(len(response.data["days"]), 1)
        self.assertEqual(response.data["days"][0]["date"], "2026-04-01")
        self.assertEqual(len(response.data["days"][0]["plans"]), 1)
        self.assertEqual(response.data["days"][0]["plans"][0]["plan_id"], str(plan.plan_id))
        self.assertEqual(response.data["days"][0]["plans"][0]["title"], "Season Plan")
        self.assertEqual(len(response.data["days"][0]["plans"][0]["sessions"]), 1)
        self.assertEqual(
            response.data["days"][0]["plans"][0]["sessions"][0],
            {
                "session_id": str(session.session_id),
                "title": "Session One",
                "session_type": "GROUP",
                "session_date": "2026-04-01",
                "start_time": "10:00:00",
                "end_time": "11:00:00",
                "intensity": "MEDIUM",
                "location": "Main Field",
                "squad_size": 18,
                "coach_note": "High tempo",
                "status": "COMPLETED",
            },
        )

    def test_list_defaults_to_today_when_dates_are_missing(self):
        today = date.today()
        today_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Today Plan",
            start_date=today,
            end_date=today,
            status="DRAFT",
        )
        future_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Future Plan",
            start_date="2026-05-10",
            end_date="2026-05-15",
            status="DRAFT",
        )
        TrainingSession.objects.create(
            plan=today_plan,
            title="Today Session",
            session_date=today,
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )
        TrainingSession.objects.create(
            plan=future_plan,
            title="Future Session",
            session_date="2026-05-10",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )

        response = self.client.get("/api/coach/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["start_date"], today.isoformat())
        self.assertEqual(response.data["end_date"], today.isoformat())
        self.assertEqual([day["date"] for day in response.data["days"]], [today.isoformat()])

    def test_list_groups_plan_references_under_same_day(self):
        first_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Alpha Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="DRAFT",
        )
        second_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Beta Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="DRAFT",
        )
        TrainingSession.objects.create(
            plan=first_plan,
            title="Morning Session",
            session_date="2026-04-03",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time="09:00",
            end_time="10:00",
        )
        TrainingSession.objects.create(
            plan=second_plan,
            title="Evening Session",
            session_date="2026-04-03",
            session_type=TrainingSession.SESSION_TYPE_TEAM,
            start_time="18:00",
            end_time="19:00",
        )

        response = self.client.get("/api/coach/plans/", {"start_date": "2026-04-03", "end_date": "2026-04-07"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["days"][0]["date"], "2026-04-03")
        self.assertEqual(
            [plan["title"] for plan in response.data["days"][0]["plans"]],
            ["Alpha Plan", "Beta Plan"],
        )
        self.assertEqual(
            [plan["plan_id"] for plan in response.data["days"][0]["plans"]],
            [str(first_plan.plan_id), str(second_plan.plan_id)],
        )

    def test_list_omits_days_without_sessions(self):
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Sparse Plan",
            start_date="2026-04-01",
            end_date="2026-04-07",
            status="DRAFT",
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Day One",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Day Three",
            session_date="2026-04-03",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )

        response = self.client.get("/api/coach/plans/", {"start_date": "2026-04-01", "end_date": "2026-04-07"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([day["date"] for day in response.data["days"]], ["2026-04-01", "2026-04-03"])

    def test_list_rejects_invalid_start_date_format(self):
        response = self.client.get("/api/coach/plans/", {"start_date": "bad", "end_date": "2026-04-07"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid start_date format.")
        self.assertEqual(list(response.data["expected"]), ["YYYY-MM-DD"])

    def test_list_rejects_start_date_after_end_date(self):
        response = self.client.get("/api/coach/plans/", {"start_date": "2026-04-07", "end_date": "2026-04-01"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "start_date must be less than or equal to end_date.")

    def test_list_rejects_range_longer_than_31_days(self):
        response = self.client.get("/api/coach/plans/", {"start_date": "2026-01-01", "end_date": "2026-02-15"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Date range must not exceed 31 days.")

    def test_detail_returns_screen_shaped_response(self):
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Screen Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="DRAFT",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)
        TrainingSession.objects.create(
            plan=plan,
            title="Strength Training",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time="16:00",
            end_time="17:30",
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Speed & Agility",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_TEAM,
            start_time="18:00",
            end_time="19:00",
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Ball Control Drills",
            session_date="2026-04-02",
            session_type=TrainingSession.SESSION_TYPE_INDIVIDUAL,
            start_time="16:00",
            end_time="17:00",
        )

        response = self.client.get(f"/api/coach/plans/{plan.plan_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Screen Plan")
        self.assertEqual(response.data["status"], "DRAFT")
        self.assertEqual(response.data["assigned_players_count"], 1)
        self.assertIn("assigned_players", response.data)
        self.assertIn("training_sessions", response.data)
        self.assertEqual(len(response.data["assigned_players"]), 1)
        self.assertEqual(response.data["assigned_players"][0]["name"], "Owned Player")
        self.assertEqual(
            response.data["assigned_players"][0]["position"],
            {
                "id": self.right_winger.id,
                "name": self.right_winger.name,
                "code": self.right_winger.code,
            },
        )
        self.assertEqual(len(response.data["training_sessions"]), 2)
        self.assertEqual(response.data["training_sessions"][0]["day_label"], "Wednesday, Apr 1")
        self.assertEqual(len(response.data["training_sessions"][0]["sessions"]), 2)
        self.assertEqual(response.data["training_sessions"][0]["sessions"][0]["session_type"], "GROUP")
        self.assertEqual(response.data["training_sessions"][0]["sessions"][0]["time_range"], "16:00 - 17:30")

    def test_rejects_lowercase_session_type(self):
        response = self.client.post(
            "/api/coach/plans/",
            {
                "title": "Bad Session Type Plan",
                "start_date": "2026-04-01",
                "end_date": "2026-04-02",
                "sessions": [
                    {
                        "date": "2026-04-01",
                        "title": "Session A",
                        "session_type": "group",
                    }
                ],
                "assignee_players": [{"id": str(self.player.id)}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                "detail": "Invalid session_type. Use uppercase values.",
                "expected": ["GROUP", "INDIVIDUAL", "TEAM"],
            },
        )

    def test_rejects_session_with_only_one_time(self):
        response = self.client.post(
            "/api/coach/plans/",
            {
                "title": "Bad Time Plan",
                "start_date": "2026-04-01",
                "end_date": "2026-04-02",
                "sessions": [
                    {
                        "date": "2026-04-01",
                        "title": "Session A",
                        "start_time": "10:00",
                    }
                ],
                "assignee_players": [{"id": str(self.player.id)}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_rejects_session_with_end_time_before_start_time(self):
        response = self.client.post(
            "/api/coach/plans/",
            {
                "title": "Reverse Time Plan",
                "start_date": "2026-04-01",
                "end_date": "2026-04-02",
                "sessions": [
                    {
                        "date": "2026-04-01",
                        "title": "Session A",
                        "start_time": "11:00",
                        "end_time": "10:00",
                    }
                ],
                "assignee_players": [{"id": str(self.player.id)}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("end_time", response.data)

    def test_rejects_players_not_owned_by_signed_in_coach(self):
        response = self.client.post(
            "/api/coach/plans/",
            {
                "title": "Unauthorized Player Plan",
                "start_date": "2026-04-01",
                "end_date": "2026-04-03",
                "sessions": [
                    {
                        "date": "2026-04-01",
                        "title": "Session A",
                        "start_time": "10:00",
                        "end_time": "11:00",
                    }
                ],
                "assignee_players": [{"id": str(self.other_player.id)}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid_player_ids", response.data)

    def test_rejects_plan_when_assignee_players_is_missing(self):
        response = self.client.post(
            "/api/coach/plans/",
            {
                "title": "Missing Players Plan",
                "start_date": "2026-04-01",
                "end_date": "2026-04-03",
                "sessions": [
                    {
                        "date": "2026-04-01",
                        "title": "Session A",
                        "start_time": "10:00",
                        "end_time": "11:00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["assignee_players"], ["At least one player must be selected."])
        self.assertEqual(TrainingPlan.objects.count(), 0)

    def test_rejects_plan_when_assignee_players_is_empty(self):
        response = self.client.post(
            "/api/coach/plans/",
            {
                "title": "Empty Players Plan",
                "start_date": "2026-04-01",
                "end_date": "2026-04-03",
                "sessions": [
                    {
                        "date": "2026-04-01",
                        "title": "Session A",
                        "start_time": "10:00",
                        "end_time": "11:00",
                    }
                ],
                "assignee_players": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["assignee_players"], ["At least one player must be selected."])
        self.assertEqual(TrainingPlan.objects.count(), 0)

