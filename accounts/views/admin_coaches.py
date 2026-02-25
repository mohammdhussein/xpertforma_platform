from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from accounts.models import CoachProfile

class PendingCoachesAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = CoachProfile.objects.filter(approval_status="pending").select_related("user")
        return Response([{
            "coach_id": str(x.user.id),
            "name": x.user.name,
            "email": x.user.email,
            "certificate_image": x.certificate_image.url if x.certificate_image else None,
        } for x in qs])

class ApproveCoachAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, coach_id):
        cp = get_object_or_404(CoachProfile, user_id=coach_id)
        cp.approval_status = "approved"
        cp.approved_at = timezone.now()
        cp.approved_by = request.user
        cp.rejection_reason = ""
        cp.save()
        return Response({"coach_id": str(coach_id), "status": "approved"})

class RejectCoachAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, coach_id):
        reason = request.data.get("reason", "")
        cp = get_object_or_404(CoachProfile, user_id=coach_id)
        cp.approval_status = "rejected"
        cp.rejection_reason = reason
        cp.save()
        return Response({"coach_id": str(coach_id), "status": "rejected", "reason": reason})