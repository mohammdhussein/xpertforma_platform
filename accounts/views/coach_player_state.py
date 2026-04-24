from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsApprovedCoach
from accounts.queries.coach_players_list import get_coach_players_queryset
from accounts.serializers.coach_player_state import (
    CoachPlayerStateResponseSerializer,
    CoachPlayerStateUpdateSerializer,
)
from accounts.services.coach_player_attention import build_coach_player_attention_summary


class CoachPlayerStateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedCoach]

    def patch(self, request, player_id):
        player_profile = get_object_or_404(
            get_coach_players_queryset(request.user),
            user_id=player_id,
        )
        serializer = CoachPlayerStateUpdateSerializer(
            player_profile,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        player_profile = serializer.save()
        attention_summary = build_coach_player_attention_summary(player_profile)
        response_serializer = CoachPlayerStateResponseSerializer(
            {
                "player_id": player_profile.user_id,
                "state": player_profile.state,
                "expected_return_date": player_profile.expected_return_date,
                "needs_attention": attention_summary["needs_attention"],
            }
        )
        return Response(response_serializer.data)
