from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User, UserRole


class PositionListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        player_role = Role.objects.create(role_name="Player")
        self.player = User.objects.create_user(
            email="positions@example.com",
            password="StrongPass123!",
            name="Positions User",
        )
        UserRole.objects.create(user=self.player, role=player_role)
        self.client.force_authenticate(user=self.player)

    def test_positions_endpoint_returns_seeded_positions(self):
        response = self.client.get("/api/positions/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["positions"]), 13)
        self.assertEqual(response.data["positions"][0]["name"], "Goalkeeper")
        self.assertEqual(response.data["positions"][-1]["code"], "CF")
