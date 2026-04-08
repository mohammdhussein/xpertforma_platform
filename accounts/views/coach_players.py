from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCoach
from accounts.selectors.coach_players import (
    build_coach_player_training_progress_payload,
    build_coach_players_list_payload,
)
from accounts.serializers import PlayerListResponseSerializer, PlayerTrainingProgressResponseSerializer


class CoachPlayersListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def get(self, request):
        payload = build_coach_players_list_payload(
            request.user,
            query=(request.query_params.get("q") or "").strip(),
            tab=(request.query_params.get("tab") or "all").strip(),
        )
        return Response(PlayerListResponseSerializer(payload).data)


class CoachPlayerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def get(self, request, player_id):
        payload = build_coach_player_training_progress_payload(request.user, player_id)
        return Response(PlayerTrainingProgressResponseSerializer(payload).data)

