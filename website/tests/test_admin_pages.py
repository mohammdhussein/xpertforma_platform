from django.test import Client, TestCase

from accounts.models import CoachProfile, PlayerProfile, User
from accounts.statuses import COACH_APPROVAL_APPROVED, COACH_APPROVAL_PENDING


class AdminCoachRequestsPageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            email="admin@example.com",
            password="StrongPass123!",
            name="Admin User",
            is_staff=True,
        )
        self.coach_user = User.objects.create_user(
            email="coachpending@example.com",
            password="StrongPass123!",
            name="Pending Coach",
        )
        self.pending_profile = CoachProfile.objects.create(
            user=self.coach_user,
            approval_status=COACH_APPROVAL_PENDING,
            certificate_image="coach_certificates/pending-certificate.png",
        )
        self.approved_user = User.objects.create_user(
            email="coachapproved@example.com",
            password="StrongPass123!",
            name="Approved Coach",
        )
        CoachProfile.objects.create(
            user=self.approved_user,
            approval_status=COACH_APPROVAL_APPROVED,
        )
        self.player_user = User.objects.create_user(
            email="player@example.com",
            password="StrongPass123!",
            name="Player One",
        )
        PlayerProfile.objects.create(
            user=self.player_user,
            coach=self.approved_user,
            login_status="complete",
        )

    def test_staff_page_redirects_unauthenticated_users_to_login(self):
        response = self.client.get("/staff/coach-requests/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/staff/login/", response["Location"])

    def test_login_page_renders_enhanced_sign_in_screen(self):
        response = self.client.get("/staff/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forgot password?")
        self.assertContains(response, "Secure admin access")
        self.assertContains(response, "Show")

    def test_staff_page_renders_for_staff_user(self):
        self.client.force_login(self.staff_user)

        response = self.client.get("/staff/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Overview of coach approvals and player growth.")

    def test_dashboard_shows_real_summary_data(self):
        self.client.force_login(self.staff_user)

        response = self.client.get("/staff/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending Requests")
        self.assertContains(response, "Approved Coaches")
        self.assertContains(response, "Total Players")
        self.assertEqual(response.context["dashboard_data"]["summary"]["pending_requests"], 1)
        self.assertEqual(response.context["dashboard_data"]["summary"]["approved_coaches"], 1)
        self.assertEqual(response.context["dashboard_data"]["summary"]["total_players"], 1)

    def test_staff_data_endpoint_returns_summary_and_requests(self):
        self.client.force_login(self.staff_user)

        response = self.client.get("/staff/coach-requests/data/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["pending_requests"], 1)
        self.assertEqual(payload["summary"]["approved_coaches"], 1)
        self.assertEqual(len(payload["requests"]), 1)
        self.assertEqual(payload["requests"][0]["email"], "coachpending@example.com")
        self.assertEqual(
            payload["requests"][0]["certificate_url"],
            "/media/coach_certificates/pending-certificate.png",
        )

    def test_coaches_data_endpoint_returns_real_coaches(self):
        self.client.force_login(self.staff_user)

        response = self.client.get("/staff/coaches/data/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total_coaches"], 2)
        self.assertEqual(len(payload["coaches"]), 2)
        self.assertEqual(payload["coaches"][0]["email"], "coachapproved@example.com")

    def test_players_data_endpoint_returns_real_players(self):
        self.client.force_login(self.staff_user)

        response = self.client.get("/staff/players/data/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total_players"], 1)
        self.assertEqual(payload["players"][0]["assigned_coach"], "Approved Coach")

    def test_staff_session_can_approve_request_via_existing_api(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            f"/api/admin/coaches/{self.coach_user.id}/approve/",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.pending_profile.refresh_from_db()
        self.assertEqual(self.pending_profile.approval_status, COACH_APPROVAL_APPROVED)

    def test_staff_can_toggle_coach_active_status(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(f"/staff/coaches/{self.approved_user.id}/toggle-active/")

        self.assertEqual(response.status_code, 200)
        self.approved_user.refresh_from_db()
        self.assertFalse(self.approved_user.is_active)
