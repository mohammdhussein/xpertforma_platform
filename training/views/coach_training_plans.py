from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsApprovedCoach
from training.queries.training_plans import (
    build_coach_training_plans_payload,
    build_training_plan_screen_payload,
    get_coach_training_plans_queryset,
)
from training.serializers.training_plans import (
    PlanScreenResponseSerializer,
    TrainingPlanCreateResultSerializer,
    TrainingPlanCreateSerializer,
    TrainingPlanDetailSerializer,
)
from training.services.coach_training_plans import create_coach_training_plan


class CoachTrainingPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsApprovedCoach]
    lookup_field = "plan_id"

    def get_queryset(self):
        return get_coach_training_plans_queryset(self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "partial_update", "update"]:
            return TrainingPlanCreateSerializer
        return TrainingPlanDetailSerializer

    def list(self, request, *args, **kwargs):
        payload = build_coach_training_plans_payload(
            request.user,
            start_date_str=request.query_params.get("start_date"),
            end_date_str=request.query_params.get("end_date"),
        )
        return Response(payload, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        payload = build_training_plan_screen_payload(self.get_object(), request)
        return Response(PlanScreenResponseSerializer(payload).data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        result = create_coach_training_plan(coach_user=request.user, payload=request.data)
        return Response(TrainingPlanCreateResultSerializer(result).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = TrainingPlanCreateSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TrainingPlanDetailSerializer(plan).data, status=status.HTTP_200_OK)

