from datetime import timedelta
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

from rest_framework import status, viewsets, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from accounts.models import PlayerProfile
from accounts.permissions import IsCoach
from training.models import TrainingPlan, TrainingSession, TrainingPlanPlayer
from training.serializers_coach import (
    TrainingPlanCreateSerializer,
    TrainingPlanDetailSerializer,
    SessionCreateSerializer,
    TrainingSessionSerializer,
    AssignPlayersSerializer,
)

def _daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


class CoachTrainingPlanViewSet(viewsets.ModelViewSet):
    """
    Stage 1: Plan details (create/update)
    Also hosts stage 2/3 actions via nested actions.
    """
    permission_classes = [IsAuthenticated, IsCoach]
    lookup_field = "plan_id"  # important if your pk field is plan_id

    def get_queryset(self):
        # coach can only see their own plans
        return TrainingPlan.objects.filter(creator=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "partial_update", "update"]:
            return TrainingPlanCreateSerializer
        return TrainingPlanDetailSerializer

    def create(self, request, *args, **kwargs):
        """
        Single endpoint to:
        - create training plan
        - create all sessions
        - assign players

        Expected JSON body:
        {
          "title": "Pre-season Plan",
          "start_date": "2026-03-10",
          "end_date": "2026-03-20",
          "sessions": [
            {
              "date": "2026-03-10",
              "title": "Warm-up & cardio",
              "start_time": "10:00",
              "end_time": "11:00",
              "notes": "Light session"
            },
            ...
          ],
          "assignee_players": [
            { "id": "<uuid>" },
            ...
          ]
        }
        """
        # 1) validate plan fields (no DB write yet)
        plan_payload = {
            "title": request.data.get("title"),
            "start_date": request.data.get("start_date"),
            "end_date": request.data.get("end_date"),
        }
        plan_serializer = TrainingPlanCreateSerializer(data=plan_payload)
        plan_serializer.is_valid(raise_exception=True)
        validated_plan = plan_serializer.validated_data
        start_date = validated_plan["start_date"]
        end_date = validated_plan["end_date"]

        # 2) validate and normalize sessions (no DB write yet)
        sessions = request.data.get("sessions") or []
        if not isinstance(sessions, list):
            raise serializers.ValidationError({"detail": "sessions must be a list."})

        normalized_sessions = []
        for sess in sessions:
            day_str = sess.get("date")
            if not day_str:
                raise serializers.ValidationError(
                    {"detail": "Each session must include a 'date' field."}
                )

            d = parse_date(day_str)
            if not d:
                raise serializers.ValidationError(
                    {"detail": f"Invalid session date format: {day_str}. Use YYYY-MM-DD."}
                )

            # validate within plan range using validated start/end
            if d < start_date or d > end_date:
                raise serializers.ValidationError(
                    {"detail": f"Session date {day_str} is outside plan date range."}
                )

            # validate time/title/notes via existing serializer
            session_payload = {
                "title": sess.get("title", ""),
                "start_time": sess.get("start_time"),
                "end_time": sess.get("end_time"),
                "notes": sess.get("notes", ""),
            }
            s = SessionCreateSerializer(data=session_payload)
            s.is_valid(raise_exception=True)
            v = s.validated_data
            normalized_sessions.append(
                {
                    "session_date": d,
                    "title": v.get("title", ""),
                    "start_time": v.get("start_time"),
                    "end_time": v.get("end_time"),
                    "notes": v.get("notes", ""),
                }
            )

        # 3) validate assignee players (no DB write yet)
        assignee_players = request.data.get("assignee_players") or []
        if not isinstance(assignee_players, list):
            raise serializers.ValidationError({"detail": "assignee_players must be a list."})

        player_ids_raw = []
        for item in assignee_players:
            if not isinstance(item, dict) or "id" not in item:
                raise serializers.ValidationError(
                    {"detail": "Each assignee_players item must be an object with an 'id' field."}
                )
            player_ids_raw.append(item["id"])

        allowed_ids = set()
        if player_ids_raw:
            assign_serializer = AssignPlayersSerializer(data={"player_ids": player_ids_raw})
            assign_serializer.is_valid(raise_exception=True)
            requested_ids = set(assign_serializer.validated_data["player_ids"])

            # only allow assigning your own players
            allowed_ids = set(
                request.user.coached_players.filter(user_id__in=requested_ids).values_list("user_id", flat=True)
            )

        # 4) perform DB writes atomically
        with transaction.atomic():
            # create plan
            plan = plan_serializer.save(creator=request.user, status="draft")

            # create sessions
            created_sessions = []
            for sess in normalized_sessions:
                session = TrainingSession.objects.create(
                    plan=plan,
                    session_date=sess["session_date"],
                    title=sess["title"],
                    start_time=sess["start_time"],
                    end_time=sess["end_time"],
                    notes=sess["notes"],
                )
                created_sessions.append(session)

            # create player assignments
            if allowed_ids:
                TrainingPlanPlayer.objects.bulk_create(
                    [
                        TrainingPlanPlayer(plan=plan, player_id=pid, assigned_by=request.user)
                        for pid in allowed_ids
                    ]
                )

        # 5) build response
        plan_data = TrainingPlanDetailSerializer(plan).data
        sessions_data = TrainingSessionSerializer(created_sessions, many=True).data

        return Response(
            {
                "message": "Training plan (with sessions and players) created successfully.",
                "plan": plan_data,
                "sessions": sessions_data,
                "assigned_player_ids": [str(pid) for pid in allowed_ids],
            },
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = TrainingPlanCreateSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TrainingPlanDetailSerializer(plan).data, status=200)



    