from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import BlacklistableJWTAuthentication
from accounts.models import CoachProfile
from accounts.queries.admin_coach_approval import get_pending_coach_profiles_queryset
from accounts.serializers.admin_coach_approval import CoachApprovalActionSerializer, PendingCoachSerializer
from accounts.services.admin_coach_approval import approve_coach_profile, reject_coach_profile

class PendingCoachesAPIView(APIView):
    authentication_classes = [SessionAuthentication, BlacklistableJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        queryset = get_pending_coach_profiles_queryset()
        return Response(PendingCoachSerializer(queryset, many=True).data)

class ApproveCoachAPIView(APIView):
    authentication_classes = [SessionAuthentication, BlacklistableJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, coach_id):
        coach_profile = get_object_or_404(CoachProfile, user_id=coach_id)
        payload = approve_coach_profile(coach_profile, request.user)
        return Response(CoachApprovalActionSerializer(payload).data)

class RejectCoachAPIView(APIView):
    authentication_classes = [SessionAuthentication, BlacklistableJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, coach_id):
        reason = request.data.get("reason", "")
        coach_profile = get_object_or_404(CoachProfile, user_id=coach_id)
        payload = reject_coach_profile(coach_profile, reason=reason)
        return Response(CoachApprovalActionSerializer(payload).data)
