from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import TrainingPlan, TrainingPlanPlayer, TrainingSession


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
            position_label=self.right_winger.name,
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
            position_label=self.center_back.name,
        )

        self.client.force_authenticate(user=self.coach)

    def test_list_returns_plans_wrapped_in_key(self):
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Season Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="draft",
        )
        TrainingSession.objects.create(
            plan=plan,
            title="Session One",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player, assigned_by=self.coach)

        response = self.client.get("/api/coach/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("plans", response.data)
        self.assertEqual(len(response.data["plans"]), 1)
        self.assertEqual(response.data["plans"][0]["title"], "Season Plan")
        self.assertEqual(response.data["plans"][0]["total_sessions"], 1)
        self.assertEqual(response.data["plans"][0]["assigned_players_count"], 1)

    def test_detail_returns_screen_shaped_response(self):
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Screen Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="draft",
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
        self.assertEqual(response.data["training_sessions"][0]["sessions"][0]["time_range"], "16:00 - 17:30")

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

