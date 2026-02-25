from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from accounts.permissions import IsCoach
from accounts.serializers.coach import CoachCreatePlayerSerializer


class CoachCreatePlayerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def post(self, request):
        s = CoachCreatePlayerSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user, pwd, position = s.create(s.validated_data, coach_user=request.user)

        return Response({
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "position": position,
            "temp_password": pwd
        }, status=status.HTTP_201_CREATED)
