from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import PlayerProfile, Position, Role, User, UserRole
from training.models import PlayerCheckin
from training.services.player_checkin import compute_readiness_score
from training.statuses import SleepQuality


CHECKIN_SUBMIT_URL   = "/api/player/checkins/"
CHECKIN_STATUS_URL   = "/api/player/checkins/today/status/"

VALID_PAYLOAD = {
    "sleep_hours":   7.5,
    "sleep_quality": SleepQuality.GOOD,
    "mood":          4,
    "sore_zones":    ["knee"],
}


def make_player(email="checkinplayer@example.com"):
    player_role = Role.objects.get_or_create(role_name="Player")[0]
    user = User.objects.create_user(email=email, password="StrongPass123!", name="Checkin Player")
    UserRole.objects.create(user=user, role=player_role)
    striker = Position.objects.get(code="ST")
    PlayerProfile.objects.create(user=user, position=striker, login_status="complete")
    return user


class ReadinessScoreFormulaTests(TestCase):
    """Pure unit tests — no DB, no HTTP."""

    def test_perfect_inputs_give_high_score(self):
        score = compute_readiness_score(
            sleep_hours=8,
            sleep_quality=SleepQuality.GREAT,
            mood=5,
            sore_zones=[],
        )
        self.assertEqual(score, 100)

    def test_poor_sleep_zero_mood_many_zones_gives_low_score(self):
        score = compute_readiness_score(
            sleep_hours=0,
            sleep_quality=SleepQuality.POOR,
            mood=1,
            sore_zones=["knee", "calf", "ankle_foot"],
        )
        self.assertLessEqual(score, 15)

    def test_soreness_penalty_capped_at_15(self):
        score_three_zones = compute_readiness_score(8, SleepQuality.GREAT, 5, ["knee", "calf", "ankle_foot"])
        score_six_zones   = compute_readiness_score(8, SleepQuality.GREAT, 5, ["knee", "calf", "ankle_foot", "shoulders", "hamstring", "hip_groin"])
        self.assertEqual(score_three_zones, score_six_zones)

    def test_score_clamped_to_0_100(self):
        score = compute_readiness_score(24, SleepQuality.GREAT, 5, [])
        self.assertLessEqual(score, 100)
        self.assertGreaterEqual(score, 0)

    def test_formula_mid_values(self):
        score = compute_readiness_score(
            sleep_hours=6,
            sleep_quality=SleepQuality.FAIR,
            mood=3,
            sore_zones=["knee"],
        )
        # hours: min(6/8,1)*40=30, quality: 0.5*20=10, mood: (2/4)*25=12.5, penalty: 5
        # raw = 30 + 10 + 12.5 + 15 - 5 = 62.5 → 62 (banker's rounding: round-half-to-even)
        self.assertEqual(score, 62)


class TodayCheckinStatusAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player = make_player()
        self.client.force_authenticate(user=self.player)

    def test_returns_submitted_false_when_no_checkin(self):
        response = self.client.get(CHECKIN_STATUS_URL)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["submitted"])
        self.assertIsNone(response.data["checkin"])

    def test_returns_checkin_when_exists(self):
        PlayerCheckin.objects.create(
            player=self.player,
            date=date.today(),
            sleep_hours="7.00",
            sleep_quality=SleepQuality.GOOD,
            mood=4,
            sore_zones=[],
            readiness_score=85,
        )
        response = self.client.get(CHECKIN_STATUS_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["submitted"])
        self.assertIsNotNone(response.data["checkin"])
        self.assertEqual(response.data["checkin"]["mood"], 4)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(CHECKIN_STATUS_URL)
        self.assertEqual(response.status_code, 401)


class SubmitCheckinAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.player = make_player()
        self.client.force_authenticate(user=self.player)

    def test_submit_creates_checkin_and_returns_201(self):
        response = self.client.post(CHECKIN_SUBMIT_URL, VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIn("readiness_score", response.data)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["mood"], 4)
        self.assertEqual(PlayerCheckin.objects.filter(player=self.player).count(), 1)

    def test_submit_returns_409_when_already_submitted_today(self):
        self.client.post(CHECKIN_SUBMIT_URL, VALID_PAYLOAD, format="json")
        response = self.client.post(CHECKIN_SUBMIT_URL, VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 409)

    def test_submit_returns_400_on_invalid_sore_zone(self):
        payload = {**VALID_PAYLOAD, "sore_zones": ["not_a_real_zone"]}
        response = self.client.post(CHECKIN_SUBMIT_URL, payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_submit_returns_400_on_mood_out_of_range(self):
        payload = {**VALID_PAYLOAD, "mood": 6}
        response = self.client.post(CHECKIN_SUBMIT_URL, payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_submit_returns_400_on_sleep_hours_above_24(self):
        payload = {**VALID_PAYLOAD, "sleep_hours": 25}
        response = self.client.post(CHECKIN_SUBMIT_URL, payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_submit_returns_400_on_invalid_sleep_quality(self):
        payload = {**VALID_PAYLOAD, "sleep_quality": "excellent"}
        response = self.client.post(CHECKIN_SUBMIT_URL, payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.post(CHECKIN_SUBMIT_URL, VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 401)

    def test_empty_sore_zones_accepted(self):
        payload = {**VALID_PAYLOAD, "sore_zones": []}
        response = self.client.post(CHECKIN_SUBMIT_URL, payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sore_zones"], [])
