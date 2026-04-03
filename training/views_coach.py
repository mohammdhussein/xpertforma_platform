from datetime import timedelta
from django.db import transaction
from django.db.models import Count
from django.utils.dateparse import parse_date

from rest_framework import status, viewsets, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsCoach
from accounts.serializers.position import build_position_payload
from training.models import TrainingPlan, TrainingSession, TrainingPlanPlayer
from training.serializers_coach import (
    PlanScreenResponseSerializer,
    TrainingPlanCreateSerializer,
    TrainingPlanDetailSerializer,
    SessionCreateSerializer,
    TrainingSessionSerializer,
    AssignPlayersSerializer,
)


def _build_time_range(start_time, end_time):
    if not start_time or not end_time:
        return ""
    return f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"


def _day_label(value):
    return f"{value.strftime('%A')}, {value.strftime('%b')} {value.day}"


class CoachTrainingPlanViewSet(viewsets.ModelViewSet):
    """
    Stage 1: Plan details (create/update)
    Also hosts stage 2/3 actions via nested actions.
    """
    permission_classes = [IsAuthenticated, IsCoach]
    lookup_field = "plan_id"  # important if your pk field is plan_id

    def get_queryset(self):
        # coach can only see their own plans
        return (
            TrainingPlan.objects
            .filter(creator=self.request.user)
            .annotate(
                total_sessions=Count("sessions", distinct=True),
                assigned_players=Count("trainingplanplayer", distinct=True),
            )
            .order_by("-start_date", "-end_date")
        )

    def get_serializer_class(self):
        if self.action in ["create", "partial_update", "update"]:
            return TrainingPlanCreateSerializer
        return TrainingPlanDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"plans": serializer.data}, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        plan = self.get_object()
        assigned_rows = (
            TrainingPlanPlayer.objects
            .filter(plan=plan)
            .select_related("player", "player__player_profile", "player__player_profile__position")
            .order_by("player__name")
        )

        assigned_players = []
        for row in assigned_rows:
            player_profile = getattr(row.player, "player_profile", None)
            avatar_url = None
            if player_profile and getattr(player_profile, "avatar", None):
                avatar_url = request.build_absolute_uri(player_profile.avatar.url)

            assigned_players.append(
                {
                    "id": row.player.id,
                    "name": row.player.name,
                    "position": build_position_payload(
                        getattr(player_profile, "position", None),
                        getattr(player_profile, "position_label", ""),
                    ),
                    "avatar_url": avatar_url,
                }
            )

        grouped_sessions = []
        current_date = None
        current_group = None
        for session in plan.sessions.all().order_by("session_date", "start_time"):
            if session.session_date != current_date:
                current_date = session.session_date
                current_group = {
                    "session_date": session.session_date,
                    "day_label": _day_label(session.session_date),
                    "sessions": [],
                }
                grouped_sessions.append(current_group)

            current_group["sessions"].append(
                {
                    "session_id": session.session_id,
                    "title": session.title or plan.title,
                    "session_type": session.session_type,
                    "start_time": session.start_time,
                    "end_time": session.end_time,
                    "time_range": _build_time_range(session.start_time, session.end_time),
                }
            )

        payload = {
            **TrainingPlanDetailSerializer(plan).data,
            "assigned_players": assigned_players,
            "training_sessions": grouped_sessions,
        }
        return Response(PlanScreenResponseSerializer(payload).data, status=status.HTTP_200_OK)

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
                "session_type": sess.get("session_type", TrainingSession.SESSION_TYPE_GROUP),
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
                    "session_type": v.get("session_type", TrainingSession.SESSION_TYPE_GROUP),
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
            invalid_ids = requested_ids - allowed_ids
            if invalid_ids:
                raise serializers.ValidationError(
                    {
                        "assignee_players": [
                            "You can only assign players currently linked to the signed-in coach."
                        ],
                        "invalid_player_ids": [str(player_id) for player_id in sorted(invalid_ids)],
                    }
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
                    session_type=sess["session_type"],
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



    
