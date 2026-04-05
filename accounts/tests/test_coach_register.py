from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, User


class CoachRegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_coach_accepts_certificate_image_path(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "name": "Coach Path",
                "email": "coachpath@example.com",
                "password": "StrongPass123!",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="coachpath@example.com")
        coach_profile = CoachProfile.objects.get(user=user)
        self.assertEqual(coach_profile.certificate_image.name, "coach_certificates/certificate.png")
        self.assertEqual(response.data["approval_status"], "PENDING")

    def test_register_coach_rejects_blank_certificate_image_path(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "name": "Coach Path",
                "email": "coachblank@example.com",
                "password": "StrongPass123!",
                "certificate_image": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["certificate_image"], ["Certificate image path is required."])
