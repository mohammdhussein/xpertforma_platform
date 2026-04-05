from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CoachProfile
from accounts.serializers.admin import CoachApprovalActionSerializer, PendingCoachSerializer
from accounts.services.admin_coaches import approve_coach_profile, reject_coach_profile
from accounts.statuses import COACH_APPROVAL_PENDING

class PendingCoachesAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        queryset = CoachProfile.objects.filter(approval_status__iexact=COACH_APPROVAL_PENDING).select_related("user")
        return Response(PendingCoachSerializer(queryset, many=True).data)

class ApproveCoachAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, coach_id):
        coach_profile = get_object_or_404(CoachProfile, user_id=coach_id)
        payload = approve_coach_profile(coach_profile, request.user)
        return Response(CoachApprovalActionSerializer(payload).data)

class RejectCoachAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, coach_id):
        reason = request.data.get("reason", "")
        coach_profile = get_object_or_404(CoachProfile, user_id=coach_id)
        payload = reject_coach_profile(coach_profile, reason=reason)
        return Response(CoachApprovalActionSerializer(payload).data)
