import time

from django.core.cache import cache
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from accounts.serializers.auth import CoachRegisterSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from accounts.serializers.auth import (
    CompleteSetPasswordSerializer,
    LoginTokenOnlySerializer,
    RefreshTokenSerializer,
)


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


class RefreshAPIView(TokenRefreshView):
    serializer_class = RefreshTokenSerializer


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            raise serializers.ValidationError({"refresh": ["This field is required."]})

        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError as exc:
            raise serializers.ValidationError({"refresh": [str(exc)]}) from exc

        access_token = request.auth
        jti = access_token["jti"]
        ttl = max(int(access_token["exp"]) - int(time.time()), 0)
        if ttl > 0:
            cache.set(f"blacklisted_jti_{jti}", True, timeout=ttl)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class CompleteSetPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CompleteSetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": str(user.id),
                "email": user.email,
                "message": "Password set successfully.",
            },
            status=status.HTTP_200_OK,
        )
