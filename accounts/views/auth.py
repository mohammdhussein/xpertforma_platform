from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from accounts.serializers.auth import CoachRegisterSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from accounts.serializers.auth import LoginTokenOnlySerializer


class CoachRegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = CoachRegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response({
            "id": str(user.id),
            "email": user.email,
            "approval_status": user.coach_profile.approval_status,
            "message": "Registration submitted. Please wait for admin approval."
        }, status=status.HTTP_201_CREATED)




class LoginAPIView(TokenObtainPairView):
    serializer_class = LoginTokenOnlySerializer
