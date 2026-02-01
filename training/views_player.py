from datetime import datetime
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsPlayer
from training.models import TrainingPlan, TrainingSession, TrainingPlanPlayer
from training.serializers_player import (
    PlayerTrainingPlanSerializer,
    PlayerTrainingSessionSerializer,
)

class PlayerMyPlansAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        user = request.user

        # Join through TrainingPlanPlayer to get assigned_at info
        assignments = (
            TrainingPlanPlayer.objects
            .filter(player=user)
            .select_related("plan")
            .order_by("-assigned_at")
        )

        # Attach assigned_at to serializer output
        plans = []
        for a in assignments:
            plan = a.plan
            plan.assigned_at = a.assigned_at  # dynamic attribute (safe for serialization)
            plans.append(plan)

        serializer = PlayerTrainingPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PlayerMySessionsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        user = request.user

        # Get all plan IDs assigned to this player
        plan_ids = TrainingPlanPlayer.objects.filter(player=user).values_list("plan_id", flat=True)

        qs = TrainingSession.objects.filter(plan_id__in=plan_ids).select_related("plan")

        # Optional filters for calendar usage
        # ?date=YYYY-MM-DD  OR  ?from=YYYY-MM-DD&to=YYYY-MM-DD
        date_str = request.query_params.get("date")
        from_str = request.query_params.get("from")
        to_str = request.query_params.get("to")

        if date_str:
            d = parse_date(date_str)
            if not d:
                return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)
            qs = qs.filter(session_date=d)

        elif from_str and to_str:
            d1 = parse_date(from_str)
            d2 = parse_date(to_str)
            if not d1 or not d2:
                return Response({"detail": "Invalid from/to format. Use YYYY-MM-DD."}, status=400)
            qs = qs.filter(session_date__range=[d1, d2])

        qs = qs.order_by("session_date", "start_time")

        serializer = PlayerTrainingSessionSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
