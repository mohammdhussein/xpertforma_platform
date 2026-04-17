from datetime import date

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.serializers.player_home import PlayerHomeSerializer
from training.services.player_home import build_player_home


class PlayerHomeAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        data = build_player_home(request.user, date.today())
        return Response(PlayerHomeSerializer(data).data)
