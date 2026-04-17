from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.serializers.player_checkin import (
    CheckinDetailSerializer,
    SubmitCheckinSerializer,
    TodayStatusSerializer,
)
from training.services.player_checkin import get_today_status, submit_checkin


class TodayCheckinStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        payload = get_today_status(request.user)
        return Response(TodayStatusSerializer(payload).data)


class SubmitCheckinAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def post(self, request):
        serializer = SubmitCheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkin = submit_checkin(request.user, **serializer.validated_data)
        return Response(CheckinDetailSerializer(checkin).data, status=HTTP_201_CREATED)
