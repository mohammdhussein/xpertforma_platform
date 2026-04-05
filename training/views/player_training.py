from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.selectors.player_training import build_player_training_day_payload
from training.services.player_training import update_player_session_status


class PlayerTrainingDayAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        payload = build_player_training_day_payload(
            request.user,
            date_str=request.query_params.get("date"),
        )
        return Response(payload)


class PlayerSessionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def post(self, request, session_id):
        payload = update_player_session_status(
            player_user=request.user,
            session_id=session_id,
            new_status=request.data.get("status"),
        )
        return Response(payload)

