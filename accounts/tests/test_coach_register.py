from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CoachProfile, User


class CoachRegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_coach_accepts_name_parts_and_certificate_image_path(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "first_name": "Coach",
                "last_name": "Path",
                "email": "coachpath@example.com",
                "password": "StrongPass123!",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="coachpath@example.com")
        coach_profile = CoachProfile.objects.get(user=user)
        self.assertEqual(user.first_name, "Coach")
        self.assertEqual(user.last_name, "Path")
        self.assertEqual(user.name, "Coach Path")
        self.assertEqual(coach_profile.certificate_image.name, "coach_certificates/certificate.png")
        self.assertIsNone(coach_profile.phone_number)
        self.assertEqual(response.data["approval_status"], "PENDING")

    def test_register_coach_supports_name_parts_and_phone_number(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "first_name": "Coach",
                "last_name": "Path",
                "phone_number": "0501112222",
                "email": "coachparts@example.com",
                "password": "StrongPass123!",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="coachparts@example.com")
        coach_profile = CoachProfile.objects.get(user=user)
        self.assertEqual(user.first_name, "Coach")
        self.assertEqual(user.last_name, "Path")
        self.assertEqual(user.name, "Coach Path")
        self.assertEqual(coach_profile.phone_number, "0501112222")
        self.assertEqual(coach_profile.certificate_image.name, "coach_certificates/certificate.png")
        self.assertEqual(response.data["approval_status"], "PENDING")

    def test_register_coach_rejects_blank_certificate_image_path(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "first_name": "Coach",
                "last_name": "Path",
                "email": "coachblank@example.com",
                "password": "StrongPass123!",
                "certificate_image": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["certificate_image"], ["Certificate image path is required."])

    def test_register_coach_requires_first_name(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "last_name": "Coach",
                "email": "nonamecoach@example.com",
                "password": "StrongPass123!",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["first_name"], ["This field is required."])

    def test_register_coach_requires_last_name(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "first_name": "NoLast",
                "email": "nonamecoach@example.com",
                "password": "StrongPass123!",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["last_name"], ["This field is required."])

    def test_register_coach_rejects_removed_name_field_contract(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "name": "Legacy Coach",
                "email": "legacycoach@example.com",
                "password": "StrongPass123!",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["first_name"], ["This field is required."])
        self.assertEqual(response.data["last_name"], ["This field is required."])

    def test_register_coach_rejects_name_parts_longer_than_stored_name_limit(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "first_name": "A" * 60,
                "last_name": "B" * 60,
                "email": "toolongcoach@example.com",
                "password": "StrongPass123!",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["last_name"],
            ["Combined first_name and last_name must be 120 characters or fewer."],
        )

    def test_register_coach_rejects_common_password(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "first_name": "Coach",
                "last_name": "Common",
                "email": "commoncoach@example.com",
                "password": "password123",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_register_coach_rejects_numeric_password(self):
        response = self.client.post(
            "/api/auth/register/coach/",
            {
                "first_name": "Coach",
                "last_name": "Numeric",
                "email": "numericcoach@example.com",
                "password": "12345678",
                "certificate_image": "coach_certificates/certificate.png",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
