from zoneinfo import ZoneInfo
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsApprovedCoach
from accounts.queries.coach_dashboard import build_coach_dashboard_payload
from accounts.serializers.coach_dashboard import CoachDashboardSerializer


def _start_of_week_sunday(date_value):
    return date_value - timedelta(days=(date_value.weekday() + 1) % 7)


def _dashboard_now():
    dashboard_timezone = ZoneInfo(getattr(settings, "APP_LOCAL_TIME_ZONE", "Asia/Jerusalem"))
    return timezone.localtime(timezone.now(), dashboard_timezone)


class CoachDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedCoach]

    def get(self, request):
        now = _dashboard_now()
        payload = build_coach_dashboard_payload(request.user, now=now)
        return Response(CoachDashboardSerializer(payload).data)
