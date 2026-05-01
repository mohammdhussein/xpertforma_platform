from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.serializers.player_performance import PlayerPerformanceSerializer
from training.services.player_performance import build_player_performance_payload


class PlayerPerformanceAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        payload = build_player_performance_payload(
            request.user,
            start_date_str=request.query_params.get("start_date"),
            end_date_str=request.query_params.get("end_date"),
        )
        return Response(PlayerPerformanceSerializer(payload).data)
