from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.queries.player_training_day import build_player_training_day_payload


class PlayerTrainingDayAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        payload = build_player_training_day_payload(
            request.user,
            date_str=request.query_params.get("date"),
        )
        return Response(payload)

