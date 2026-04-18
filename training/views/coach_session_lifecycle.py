from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCoach
from training.serializers.coach_session_lifecycle import CoachSessionStartSerializer
from training.services.coach_session_lifecycle import end_session, start_session


class CoachSessionStartAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def post(self, request, plan_id, session_id):
        serializer = CoachSessionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = start_session(
            coach_user=request.user,
            plan_id=plan_id,
            session_id=session_id,
            present_player_ids=serializer.validated_data["presentPlayerIds"],
        )
        return Response(payload)


class CoachSessionEndAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def post(self, request, plan_id, session_id):
        payload = end_session(
            coach_user=request.user,
            plan_id=plan_id,
            session_id=session_id,
        )
        return Response(payload)
