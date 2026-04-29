from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, PlayerProfile, Position, Role, User, UserRole
from training.models import (
    SessionAttendance,
    SessionLifecycle,
    TrainingPlan,
    TrainingPlanPlayer,
    TrainingSession,
)


class CoachSessionLifecycleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        coach_role = Role.objects.create(role_name="Coach")
        player_role = Role.objects.create(role_name="Player")
        position = Position.objects.get(code="RW")

        self.coach = User.objects.create_user(
            email="lifecyclecoach@example.com",
            password="StrongPass123!",
            name="Lifecycle Coach",
        )
        UserRole.objects.create(user=self.coach, role=coach_role)
        CoachProfile.objects.create(user=self.coach, approval_status="APPROVED")

        self.other_coach = User.objects.create_user(
            email="othercoachlife@example.com",
            password="StrongPass123!",
            name="Other Coach",
        )
        UserRole.objects.create(user=self.other_coach, role=coach_role)
        CoachProfile.objects.create(user=self.other_coach, approval_status="APPROVED")

        self.player_a = User.objects.create_user(
            email="playera@example.com",
            password="StrongPass123!",
            name="Player A",
        )
        UserRole.objects.create(user=self.player_a, role=player_role)
        PlayerProfile.objects.create(user=self.player_a, coach=self.coach, position=position)

        self.player_b = User.objects.create_user(
            email="playerb@example.com",
            password="StrongPass123!",
            name="Player B",
        )
        UserRole.objects.create(user=self.player_b, role=player_role)
        PlayerProfile.objects.create(user=self.player_b, coach=self.coach, position=position)

        self.unassigned_player = User.objects.create_user(
            email="unassigned@example.com",
            password="StrongPass123!",
            name="Unassigned Player",
        )
        UserRole.objects.create(user=self.unassigned_player, role=player_role)
        PlayerProfile.objects.create(
            user=self.unassigned_player,
            coach=self.coach,
            position=position,
        )

        self.plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Lifecycle Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="ACTIVE",
        )
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player_a, assigned_by=self.coach)
        TrainingPlanPlayer.objects.create(plan=self.plan, player=self.player_b, assigned_by=self.coach)

        self.session = TrainingSession.objects.create(
            plan=self.plan,
            title="Lifecycle Session",
            session_date="2026-04-01",
            session_type=TrainingSession.SESSION_TYPE_GROUP,
            start_time="10:00",
            end_time="11:00",
        )

        self.start_url = (
            f"/api/coach/plans/{self.plan.plan_id}/sessions/{self.session.session_id}/start/"
        )
        self.end_url = (
            f"/api/coach/plans/{self.plan.plan_id}/sessions/{self.session.session_id}/end/"
        )

    # ----- start: happy paths and validation -----

    def test_start_sets_in_progress_and_records_present_players(self):
        self.client.force_authenticate(user=self.coach)
        response = self.client.post(
            self.start_url,
            {"presentPlayerIds": [str(self.player_a.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_id"], str(self.session.session_id))
        self.assertEqual(response.data["title"], "Lifecycle Session")
        self.assertEqual(response.data["session_type"], "GROUP")
        self.assertEqual(response.data["session_date"], "2026-04-01")
        self.assertEqual(response.data["status"], "IN_PROGRESS")
        self.assertNotIn("time_range", response.data)
        self.assertNotIn("squad_size", response.data)
        self.assertEqual(response.data["lifecycle"]["status"], "IN_PROGRESS")
        self.assertIsNotNone(response.data["lifecycle"]["started_at"])
        self.assertIsNone(response.data["lifecycle"]["ended_at"])
        self.assertEqual(response.data["present_player_ids"], [str(self.player_a.id)])
        self.assertEqual(response.data["missed_player_ids"], [str(self.player_b.id)])

        lifecycle = SessionLifecycle.objects.get(session=self.session)
        self.assertEqual(lifecycle.status, SessionLifecycle.IN_PROGRESS)
        self.assertEqual(lifecycle.started_by, self.coach)
        self.assertTrue(
            SessionAttendance.objects
            .filter(session=self.session, player=self.player_a, status="PRESENT")
            .exists()
        )

    def test_start_with_empty_present_list_marks_all_assigned_as_missed(self):
        self.client.force_authenticate(user=self.coach)
        response = self.client.post(self.start_url, {"presentPlayerIds": []}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["present_player_ids"], [])
        self.assertCountEqual(
            response.data["missed_player_ids"],
            [str(self.player_a.id), str(self.player_b.id)],
        )

    def test_start_rejects_unassigned_player_id(self):
        self.client.force_authenticate(user=self.coach)
        response = self.client.post(
            self.start_url,
            {"presentPlayerIds": [str(self.unassigned_player.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not assigned to this plan", response.data["detail"])
        self.assertIn("expected", response.data)

    def test_start_returns_409_when_already_started(self):
        SessionLifecycle.objects.create(
            session=self.session,
            status=SessionLifecycle.IN_PROGRESS,
        )
        self.client.force_authenticate(user=self.coach)
        response = self.client.post(self.start_url, {"presentPlayerIds": []}, format="json")

        self.assertEqual(response.status_code, 409)

    def test_start_returns_404_for_session_not_in_plan(self):
        other_plan = TrainingPlan.objects.create(
            creator=self.coach,
            title="Other Plan",
            start_date="2026-04-01",
            end_date="2026-04-05",
            status="ACTIVE",
        )
        self.client.force_authenticate(user=self.coach)
        response = self.client.post(
            f"/api/coach/plans/{other_plan.plan_id}/sessions/{self.session.session_id}/start/",
            {"presentPlayerIds": []},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_start_returns_403_for_other_coach(self):
        self.client.force_authenticate(user=self.other_coach)
        response = self.client.post(self.start_url, {"presentPlayerIds": []}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_start_requires_authentication(self):
        response = self.client.post(self.start_url, {"presentPlayerIds": []}, format="json")
        self.assertEqual(response.status_code, 401)

    # ----- end: happy paths and validation -----

    def test_end_completes_in_progress_session(self):
        SessionLifecycle.objects.create(
            session=self.session,
            status=SessionLifecycle.IN_PROGRESS,
        )
        SessionAttendance.objects.create(
            session=self.session,
            player=self.player_a,
            status=SessionAttendance.PRESENT,
        )

        self.client.force_authenticate(user=self.coach)
        response = self.client.post(self.end_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["lifecycle"]["status"], "COMPLETED")
        self.assertIsNotNone(response.data["lifecycle"]["ended_at"])
        self.assertEqual(response.data["present_player_ids"], [str(self.player_a.id)])
        self.assertEqual(response.data["missed_player_ids"], [str(self.player_b.id)])

        lifecycle = SessionLifecycle.objects.get(session=self.session)
        self.assertEqual(lifecycle.status, SessionLifecycle.COMPLETED)
        self.assertEqual(lifecycle.ended_by, self.coach)

    def test_end_returns_409_when_not_in_progress(self):
        self.client.force_authenticate(user=self.coach)
        response = self.client.post(self.end_url, {}, format="json")
        self.assertEqual(response.status_code, 409)

        SessionLifecycle.objects.create(
            session=self.session,
            status=SessionLifecycle.COMPLETED,
        )
        response = self.client.post(self.end_url, {}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_end_returns_403_for_other_coach(self):
        SessionLifecycle.objects.create(
            session=self.session,
            status=SessionLifecycle.IN_PROGRESS,
        )
        self.client.force_authenticate(user=self.other_coach)
        response = self.client.post(self.end_url, {}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_end_requires_authentication(self):
        response = self.client.post(self.end_url, {}, format="json")
        self.assertEqual(response.status_code, 401)
