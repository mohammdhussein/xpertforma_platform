from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.queries.player_sessions_count import build_player_sessions_count_payload


class PlayerSessionsCountAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        payload = build_player_sessions_count_payload(
            request.user,
            start_date_str=request.query_params.get("start_date"),
            end_date_str=request.query_params.get("end_date"),
        )
        return Response(payload)
