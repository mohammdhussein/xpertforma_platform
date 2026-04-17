from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.services.player_session_status import update_player_session_status


class PlayerSessionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def post(self, request, session_id):
        payload = update_player_session_status(
            player_user=request.user,
            session_id=session_id,
            new_status=request.data.get("status"),
        )
        return Response(payload)

