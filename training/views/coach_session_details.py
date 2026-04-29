from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsApprovedCoach
from training.queries.coach_session_details import build_coach_session_details_payload
from training.serializers.coach_session_details import CoachSessionDetailsSerializer


class CoachSessionDetailsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedCoach]

    def get(self, request, plan_id, session_id):
        payload = build_coach_session_details_payload(
            coach_user=request.user,
            plan_id=plan_id,
            session_id=session_id,
        )
        return Response(CoachSessionDetailsSerializer(payload).data)
