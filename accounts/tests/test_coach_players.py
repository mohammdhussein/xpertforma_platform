from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    CoachProfile,
    PlayerPerformanceSnapshot,
    PlayerProfile,
    Position,
    Role,
    User,
    UserRole,
)
from training.models import (
    PlayerSessionProgress,
    SessionAttendance,
    SessionLifecycle,
    TrainingPlan,
    TrainingPlanPlayer,
    TrainingSession,
)


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
            phone="0501234567",
            date_of_birth=date(2004, 6, 15),
        )
        UserRole.objects.create(user=self.player_one, role=self.player_role)
        PlayerProfile.objects.create(
            user=self.player_one,
            coach=self.coach,
            position=self.striker,
            height_cm=185,
            weight_kg=78,
            foot=PlayerProfile.FOOT_RIGHT,
            state=PlayerProfile.STATE_INJURED,
            expected_return_date=date(2026, 5, 1),
            avatar="player_avatars/alpha.png",
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
            state=PlayerProfile.STATE_ACTIVE,
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
                "state": "INJURED",
                "needs_attention": True,
                "expected_return_date": "2026-05-01",
                "avatar_url": "/media/player_avatars/alpha.png",
            },
        )

    def test_players_endpoint_filters_by_state_tab(self):
        response = self.client.get("/api/coach/players/?tab=NEEDS_ATTENTION")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["players"]), 1)
        self.assertEqual(response.data["players"][0]["id"], str(self.player_one.id))
        self.assertEqual(response.data["players"][0]["state"], "INJURED")
        self.assertTrue(response.data["players"][0]["needs_attention"])

    def test_not_started_training_does_not_mark_active_player_needing_attention(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Build Up Play",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=7),
            status="DRAFT",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player_two, assigned_by=self.coach)
        session = TrainingSession.objects.create(
            plan=plan,
            title="Shape Walkthrough",
            session_date=today,
            session_type=TrainingSession.SESSION_TYPE_TEAM,
            start_time=time(15, 0),
            end_time=time(16, 0),
        )
        PlayerSessionProgress.objects.create(
            player=self.player_two,
            session=session,
            status="NOT_STARTED",
        )
        SessionLifecycle.objects.create(session=session, status=SessionLifecycle.NOT_STARTED)

        response = self.client.get("/api/coach/players/")

        self.assertEqual(response.status_code, 200)
        player_two = next(
            player for player in response.data["players"]
            if player["id"] == str(self.player_two.id)
        )
        self.assertFalse(player_two["needs_attention"])

    def test_players_endpoint_rejects_lowercase_state_tab(self):
        response = self.client.get("/api/coach/players/?tab=needs_attention")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid tab. Use uppercase values.")
        self.assertEqual(
            list(response.data["expected"]),
            ["ALL", "ACTIVE", "INJURED", "NEEDS_ATTENTION"],
        )

    def test_player_profile_endpoint_returns_computed_overview_payload(self):
        today = timezone.localdate()
        now = timezone.now()
        active_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Speed & Agility Program",
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
            status="DRAFT",
        )
        completed_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Shooting Technique",
            start_date=today - timedelta(days=12),
            end_date=today - timedelta(days=9),
            status="DRAFT",
        )
        TrainingPlanPlayer.objects.create(plan=active_plan, player=self.player_one, assigned_by=self.coach)
        TrainingPlanPlayer.objects.create(plan=completed_plan, player=self.player_one, assigned_by=self.coach)

        speed_session = TrainingSession.objects.create(
            plan=active_plan,
            title="Speed & Agility Training",
            session_date=today - timedelta(days=3),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(16, 0),
            end_time=time(17, 30),
        )
        shooting_session = TrainingSession.objects.create(
            plan=active_plan,
            title="Shooting Practice",
            session_date=today - timedelta(days=2),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        tactics_session = TrainingSession.objects.create(
            plan=active_plan,
            title="Team Tactics",
            session_date=today - timedelta(days=1),
            session_type=TrainingSession.SESSION_TYPE_TEAM,
            start_time=time(16, 30),
            end_time=time(18, 0),
        )
        future_session = TrainingSession.objects.create(
            plan=active_plan,
            title="Endurance Building",
            session_date=today + timedelta(days=1),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(17, 0),
            end_time=time(18, 30),
        )
        completed_plan_session = TrainingSession.objects.create(
            plan=completed_plan,
            title="Finishing Session",
            session_date=today - timedelta(days=10),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )

        speed_progress = PlayerSessionProgress.objects.create(
            player=self.player_one,
            session=speed_session,
            status="COMPLETED",
        )
        shooting_progress = PlayerSessionProgress.objects.create(
            player=self.player_one,
            session=shooting_session,
            status="COMPLETED",
        )
        tactics_progress = PlayerSessionProgress.objects.create(
            player=self.player_one,
            session=tactics_session,
            status="IN_PROGRESS",
        )
        completed_plan_progress = PlayerSessionProgress.objects.create(
            player=self.player_one,
            session=completed_plan_session,
            status="COMPLETED",
        )

        PlayerSessionProgress.objects.filter(pk=speed_progress.pk).update(updated_at=now - timedelta(days=3))
        PlayerSessionProgress.objects.filter(pk=shooting_progress.pk).update(updated_at=now - timedelta(days=2))
        PlayerSessionProgress.objects.filter(pk=tactics_progress.pk).update(updated_at=now - timedelta(hours=2))
        PlayerSessionProgress.objects.filter(pk=completed_plan_progress.pk).update(updated_at=now - timedelta(days=5))

        PlayerPerformanceSnapshot.objects.create(
            player=self.player_one,
            recorded_by=self.coach,
            speed=88,
            stamina=70,
            strength=78,
            skills=85,
        )
        PlayerPerformanceSnapshot.objects.create(
            player=self.player_one,
            recorded_by=self.coach,
            speed=88,
            stamina=62,
            strength=78,
            skills=85,
        )

        response = self.client.get(f"/api/coach/players/{self.player_one.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["player"],
            {
                "id": str(self.player_one.id),
                "name": "Alpha Player",
                "dateOfBirth": "2004-06-15",
                "position": {
                    "id": self.striker.id,
                    "name": self.striker.name,
                    "code": self.striker.code,
                },
                "avatar_url": "/media/player_avatars/alpha.png",
                "phone": "0501234567",
                "heightCm": 185.0,
                "weightKg": 78.0,
                "foot": "RIGHT",
                "state": "INJURED",
                "expectedReturnDate": "2026-05-01",
                "needsAttention": True,
            },
        )
        self.assertEqual(
            response.data["overview"]["keyMetrics"],
            {
                "progressRate": {"value": 75, "trend": "DOWN"},
                "attendance": {"completed": 3, "total": 3, "rate": 100},
                "consistency": {"streakDays": 3},
                "focusArea": {"name": "Endurance", "trend": "DOWN"},
            },
        )
        self.assertEqual(
            response.data["overview"]["needsAttention"],
            [
                {
                    "id": "player_injured",
                    "message": "Player is currently marked as injured. Expected return date: 2026-05-01.",
                    "severity": "CRITICAL",
                },
                {
                    "id": "declining_focus_area",
                    "message": "Recent performance is declining in endurance",
                    "severity": "INFO",
                },
            ],
        )
        self.assertEqual(
            response.data["overview"]["recentActivity"],
            [
                {
                    "id": str(shooting_session.session_id),
                    "title": "Shooting Practice",
                    "date": str(today - timedelta(days=2)),
                    "startTime": "18:00",
                    "endTime": "19:00",
                    "status": "COMPLETED",
                },
                {
                    "id": str(speed_session.session_id),
                    "title": "Speed & Agility Training",
                    "date": str(today - timedelta(days=3)),
                    "startTime": "16:00",
                    "endTime": "17:30",
                    "status": "COMPLETED",
                },
                {
                    "id": str(completed_plan_session.session_id),
                    "title": "Finishing Session",
                    "date": str(today - timedelta(days=10)),
                    "startTime": "10:00",
                    "endTime": "11:00",
                    "status": "COMPLETED",
                },
            ],
        )
        self.assertEqual(
            response.data["overview"]["coachInsights"],
            [
                "Attendance is high and the player is consistent with scheduled training.",
                "The player is showing strong progress across assigned plans.",
                "Current focus area is Endurance.",
                "Recent performance in Endurance is declining.",
            ],
        )
        self.assertEqual(
            response.data["stats"],
            {
                "performanceMetrics": [
                    {"name": "Speed", "value": 88},
                    {"name": "Stamina", "value": 62},
                    {"name": "Strength", "value": 78},
                    {"name": "Skills", "value": 85},
                ],
                "achievements": {
                    "plansDone": 1,
                    "bestStreak": 3,
                },
            },
        )
        self.assertEqual(response.data["plans"][0]["title"], "Speed & Agility Program")
        self.assertEqual(response.data["plans"][0]["status"], "ACTIVE")
        self.assertEqual(response.data["plans"][0]["progress"], 50)
        self.assertEqual(response.data["plans"][0]["completedSessions"], 2)
        self.assertEqual(response.data["plans"][0]["remainingSessions"], 2)
        self.assertEqual(response.data["plans"][0]["lastActivity"], "2 hours ago")
        self.assertEqual(response.data["plans"][1]["title"], "Shooting Technique")
        self.assertEqual(response.data["plans"][1]["status"], "COMPLETED")
        self.assertEqual(response.data["plans"][1]["progress"], 100)
        self.assertEqual(response.data["plans"][1]["completedSessions"], 1)
        self.assertEqual(response.data["plans"][1]["remainingSessions"], 0)
        self.assertEqual(response.data["plans"][1]["lastActivity"], "5 days ago")

    def test_player_profile_endpoint_handles_empty_training_state(self):
        response = self.client.get(f"/api/coach/players/{self.player_two.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["player"],
            {
                "id": str(self.player_two.id),
                "name": "Beta Player",
                "dateOfBirth": None,
                "position": {
                    "id": self.central_midfielder.id,
                    "name": self.central_midfielder.name,
                    "code": self.central_midfielder.code,
                },
                "avatar_url": None,
                "phone": None,
                "heightCm": None,
                "weightKg": None,
                "foot": None,
                "state": "ACTIVE",
                "expectedReturnDate": None,
                "needsAttention": False,
            },
        )
        self.assertEqual(response.data["overview"]["needsAttention"], [])
        self.assertEqual(
            response.data["overview"]["keyMetrics"],
            {
                "progressRate": {"value": 0, "trend": "FLAT"},
                "attendance": {"completed": 0, "total": 0, "rate": 0},
                "consistency": {"streakDays": 0},
                "focusArea": {"name": None, "trend": "FLAT"},
            },
        )
        self.assertEqual(
            response.data["overview"]["coachInsights"],
            ["Not enough recent training data to generate insight."],
        )
        self.assertEqual(response.data["overview"]["recentActivity"], [])
        self.assertEqual(
            response.data["stats"],
            {
                "performanceMetrics": [
                    {"name": "Speed", "value": None},
                    {"name": "Stamina", "value": None},
                    {"name": "Strength", "value": None},
                    {"name": "Skills", "value": None},
                ],
                "achievements": {
                    "plansDone": 0,
                    "bestStreak": 0,
                },
            },
        )
        self.assertEqual(response.data["plans"], [])

    def test_player_profile_endpoint_uses_session_lifecycle_and_attendance_data(self):
        today = timezone.localdate()
        plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Match Prep",
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=3),
            status="DRAFT",
        )
        TrainingPlanPlayer.objects.create(plan=plan, player=self.player_two, assigned_by=self.coach)
        attended_session = TrainingSession.objects.create(
            plan=plan,
            title="Pressing Drill",
            session_date=today - timedelta(days=2),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        missed_session = TrainingSession.objects.create(
            plan=plan,
            title="Recovery Run",
            session_date=today - timedelta(days=1),
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time=time(12, 0),
            end_time=time(13, 0),
        )
        SessionLifecycle.objects.create(
            session=attended_session,
            status=SessionLifecycle.COMPLETED,
            ended_at=timezone.now() - timedelta(days=2),
            ended_by=self.coach,
        )
        SessionLifecycle.objects.create(
            session=missed_session,
            status=SessionLifecycle.COMPLETED,
            ended_at=timezone.now() - timedelta(days=1),
            ended_by=self.coach,
        )
        SessionAttendance.objects.create(
            session=attended_session,
            player=self.player_two,
            status=SessionAttendance.PRESENT,
            marked_by=self.coach,
        )

        response = self.client.get(f"/api/coach/players/{self.player_two.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["overview"]["keyMetrics"]["attendance"],
            {"completed": 1, "total": 2, "rate": 50},
        )
        self.assertEqual(response.data["plans"][0]["progress"], 50)
        self.assertEqual(response.data["plans"][0]["completedSessions"], 1)
        self.assertEqual(response.data["plans"][0]["remainingSessions"], 1)
        self.assertEqual(
            response.data["overview"]["recentActivity"][:2],
            [
                {
                    "id": str(missed_session.session_id),
                    "title": "Recovery Run",
                    "date": str(today - timedelta(days=1)),
                    "startTime": "12:00",
                    "endTime": "13:00",
                    "status": "MISSED",
                },
                {
                    "id": str(attended_session.session_id),
                    "title": "Pressing Drill",
                    "date": str(today - timedelta(days=2)),
                    "startTime": "10:00",
                    "endTime": "11:00",
                    "status": "COMPLETED",
                },
            ],
        )

    def test_player_profile_endpoint_preserves_custom_focus_area_override(self):
        PlayerPerformanceSnapshot.objects.create(
            player=self.player_two,
            recorded_by=self.coach,
            speed=80,
            stamina=81,
            strength=82,
            skills=83,
            focus_area_override="Finishing",
        )

        response = self.client.get(f"/api/coach/players/{self.player_two.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["overview"]["keyMetrics"]["focusArea"],
            {"name": "Finishing", "trend": "FLAT"},
        )
        self.assertEqual(
            response.data["overview"]["coachInsights"],
            ["Current focus area is Finishing."],
        )
