from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from accounts.permissions import IsCoach
from accounts.serializers_auth import CoachRegisterSerializer, PlayerCreateByCoachSerializer

class CoachRegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = CoachRegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response({"id": str(user.id), "email": user.email, "name": user.name}, status=status.HTTP_201_CREATED)


class CoachCreatePlayerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def post(self, request):
        s = PlayerCreateByCoachSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        player_user, temp_password = s.create(s.validated_data, coach_user=request.user)

        return Response({
            "id": str(player_user.id),
            "email": player_user.email,
            "name": player_user.name,
            "temp_password": temp_password
        }, status=status.HTTP_201_CREATED)
