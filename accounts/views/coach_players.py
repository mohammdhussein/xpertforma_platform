from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsApprovedCoach
from accounts.queries.coach_player_profile import (
    get_coach_player_profile_data,
)
from accounts.queries.coach_players_list import (
    build_coach_players_list_payload,
)
from accounts.serializers import PlayerListResponseSerializer, PlayerTrainingProgressResponseSerializer


class CoachPlayersListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedCoach]

    def get(self, request):
        payload = build_coach_players_list_payload(
            request.user,
            query=(request.query_params.get("q") or "").strip(),
            tab=(request.query_params.get("tab") or "ALL").strip(),
        )
        return Response(PlayerListResponseSerializer(payload).data)


class CoachPlayerProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedCoach]

    def get(self, request, player_id):
        payload = get_coach_player_profile_data(request.user, player_id)
        return Response(PlayerTrainingProgressResponseSerializer(payload).data)
