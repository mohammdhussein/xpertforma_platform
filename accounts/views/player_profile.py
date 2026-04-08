from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from accounts.serializers.player_profile import (
    PlayerProfileDetailSerializer,
    PlayerProfileUpdateSerializer,
    build_player_profile_payload,
)


class PlayerProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        player_profile = request.user.player_profile
        serializer = PlayerProfileDetailSerializer(build_player_profile_payload(player_profile))
        return Response(serializer.data)

    def patch(self, request):
        return self._update(request, partial=True)

    def put(self, request):
        return self._update(request, partial=True)

    def _update(self, request, *, partial):
        player_profile = request.user.player_profile
        serializer = PlayerProfileUpdateSerializer(
            player_profile,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        player_profile = serializer.save()
        response_serializer = PlayerProfileDetailSerializer(build_player_profile_payload(player_profile))
        return Response(response_serializer.data)
