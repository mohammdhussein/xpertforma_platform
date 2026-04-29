from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import (
    TrainingPlan,
    TrainingPlanPlayer,
    TrainingSession,
)
from training.statuses import Intensity


class CoachSessionDetailsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        coach_role = Role.objects.create(role_name="Coach")
        player_role = Role.objects.create(role_name="Player")
        self.position = Position.objects.get(code="RW")

        self.coach = User.objects.create_user(
            email="detailscoach@example.com",
            password="StrongPass123!",
            name="Details Coach",
        )
        UserRole.objects.create(user=self.coach, role=coach_role)
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")

        self.other_coach = User.objects.create_user(
            email="otherdetailscoach@example.com",
            password="StrongPass123!",
            name="Other Details Coach",
        )
        UserRole.objects.create(user=self.other_coach, role=coach_role)
        CoachProfile.objects.create(user=self.other_coach, approval_status="APPROVED")

        self.player_a = User.objects.create_user(
            email="detailsplayera@example.com",
            password="StrongPass123!",
            name="Player A",
        )
        UserRole.objects.create(user=self.player_a, role=player_role)
        PlayerProfile.objects.create(user=self.player_a, coach=self.coach, position=self.position)

        self.player_b = User.objects.create_user(
            email="detailsplayerb@example.com",
            password="StrongPass123!",
            name="Player B",
        )
        UserRole.objects.create(user=self.player_b, role=player_role)
        PlayerProfile.objects.create(user=self.player_b, coach=self.coach, position=self.position)

        self.plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Details Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="ACTIVE",
        )
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player_a, assigned_by=self.coach)
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player_b, assigned_by=self.coach)

        self.session = TrainingSession.objects.create(
            plan=self.plan,
            title="Details Session",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_TEAM,
            start_time="10:00",
            end_time="11:30",
            notes="Bring boots",
            intensity=Intensity.HIGH,
            location="Main Pitch A",
            squad_size=18,
        )
        self.url = f"/api/coach/plans/{self.plan.plan_id}/sessions/{self.session.session_id}/"

    def test_returns_short_session_details(self):
        self.client.force_authenticate(user=self.coach)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "session_id": str(self.session.session_id),
                "plan": {
                    "plan_id": str(self.plan.plan_id),
                    "title": "Details Plan",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-05",
                    "status": "ACTIVE",
                },
                "title": "Details Session",
                "session_type": "TEAM",
                "session_date": "2026-04-01",
                "start_time": "10:00:00",
                "end_time": "11:30:00",
                "intensity": "HIGH",
                "location": "Main Pitch A",
                "notes": "Bring boots",
                "status": "NOT_STARTED",
                "lifecycle": {
                    "status": "NOT_STARTED",
                    "started_at": None,
                    "ended_at": None,
                },
            },
        )

    def test_returns_404_for_session_not_in_plan(self):
        other_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Other Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="ACTIVE",
        )
        self.client.force_authenticate(user=self.coach)

        response = self.client.get(
            f"/api/coach/plans/{other_plan.plan_id}/sessions/{self.session.session_id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_returns_403_for_other_coach(self):
        self.client.force_authenticate(user=self.other_coach)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)
