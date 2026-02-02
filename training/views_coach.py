from datetime import timedelta
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

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
        # Create DRAFT plan and return plan_id for wizard step 2
        serializer = TrainingPlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = serializer.save(creator=request.user, status="draft")
        return Response(TrainingPlanDetailSerializer(plan).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = TrainingPlanCreateSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TrainingPlanDetailSerializer(plan).data, status=200)

    # -------- Stage 2: Days list (computed) --------
    @action(detail=True, methods=["get"], url_path="days")
    def days(self, request, plan_id=None):
        plan = self.get_object()

        # Count sessions per day
        counts = (
            TrainingSession.objects
            .filter(plan=plan)
            .values("session_date")
            .annotate(c=Count("session_id"))
        )
        count_map = {str(x["session_date"]): x["c"] for x in counts}

        days = []
        for d in _daterange(plan.start_date, plan.end_date):
            ds = str(d)
            days.append({
                "date": ds,
                "weekday": d.strftime("%A"),
                "sessions_count": count_map.get(ds, 0),
            })

        total_sessions = sum(x["sessions_count"] for x in days)
        return Response({
            "plan_id": str(plan.plan_id),
            "start_date": str(plan.start_date),
            "end_date": str(plan.end_date),
            "days": days,
            "total_sessions": total_sessions,
        })

    # -------- Stage 2: Add sessions for a specific day (date comes from URL) --------
    @action(detail=True, methods=["get", "post"], url_path=r"days/(?P<day>\d{4}-\d{2}-\d{2})/sessions")
    def sessions_for_day(self, request, plan_id=None, day=None):
        plan = self.get_object()

        d = parse_date(day)
        if not d:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # validate date inside plan range
        if d < plan.start_date or d > plan.end_date:
            return Response({"detail": "Day is outside plan date range."}, status=400)

        if request.method == "GET":
            qs = TrainingSession.objects.filter(plan=plan, session_date=d).order_by("start_time")
            return Response(TrainingSessionSerializer(qs, many=True).data)

        # POST create session where session_date is FROM URL
        s = SessionCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        session = TrainingSession.objects.create(
            plan=plan,
            session_date=d,                  # ✅ from URL
            title=data.get("title", ""),
            start_time=data.get("start_time", None),
            end_time=data.get("end_time", None),
            notes=data.get("notes", ""),
        )

        return Response(TrainingSessionSerializer(session).data, status=201)

    # Optional: edit/delete a session (coach only, must own the plan)
    @action(detail=True, methods=["patch", "delete"], url_path=r"sessions/(?P<session_id>[0-9a-f-]{36})")
    def edit_session(self, request, plan_id=None, session_id=None):
        plan = self.get_object()
        session = get_object_or_404(TrainingSession, session_id=session_id, plan=plan)

        if request.method == "DELETE":
            session.delete()
            return Response(status=204)

        # PATCH
        s = SessionCreateSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        for k, v in s.validated_data.items():
            setattr(session, k, v)
        session.save()
        return Response(TrainingSessionSerializer(session).data, status=200)

    # -------- Stage 3: list coach players for checkbox list --------
    @action(detail=False, methods=["get"], url_path="players")
    def coach_players(self, request):
        # returns players whose PlayerProfile.coach == request.user
        players = (
            request.user.coached_players
            .select_related("player_profile")
            .all()
        )

        result = []
        for u in players:
            pp = getattr(u, "player_profile", None)
            result.append({
                "id": str(u.id),
                "name": u.name,
                "position": getattr(pp, "position", "") if pp else "",
            })

        return Response(result)

    # -------- Stage 3: assign players (bulk) --------
    @action(detail=True, methods=["get", "post"], url_path="assignments")
    def assignments(self, request, plan_id=None):
        plan = self.get_object()

        if request.method == "GET":
            ids = list(
                TrainingPlanPlayer.objects.filter(plan=plan).values_list("player_id", flat=True)
            )
            return Response({"plan_id": str(plan.plan_id), "player_ids": [str(x) for x in ids]})

        s = AssignPlayersSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        requested_ids = set(s.validated_data["player_ids"])

        # only allow assigning your own players (Coach 1:N Players rule)
        allowed_ids = set(
            request.user.coached_players.filter(id__in=requested_ids).values_list("id", flat=True)
        )

        # strategy: make DB match exactly what's sent (checkbox save)
        # 1) delete assignments not in allowed_ids
        TrainingPlanPlayer.objects.filter(plan=plan).exclude(player_id__in=allowed_ids).delete()

        # 2) create missing assignments
        existing = set(
            TrainingPlanPlayer.objects.filter(plan=plan, player_id__in=allowed_ids)
            .values_list("player_id", flat=True)
        )

        to_create = allowed_ids - existing
        TrainingPlanPlayer.objects.bulk_create([
            TrainingPlanPlayer(plan=plan, player_id=pid, assigned_by=request.user)
            for pid in to_create
        ])

        return Response({
            "plan_id": str(plan.plan_id),
            "assigned_players": TrainingPlanPlayer.objects.filter(plan=plan).count()
        }, status=200)

    # -------- Summary for Step 3 card --------
    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, plan_id=None):
        plan = self.get_object()
        total_sessions = TrainingSession.objects.filter(plan=plan).count()
        assigned_players = TrainingPlanPlayer.objects.filter(plan=plan).count()

        return Response({
            "plan_id": str(plan.plan_id),
            "title": plan.title,
            "start_date": str(plan.start_date),
            "end_date": str(plan.end_date),
            "total_sessions": total_sessions,
            "assigned_players": assigned_players,
            "status": plan.status,
        })

    # -------- Finish wizard --------
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, plan_id=None):
        plan = self.get_object()

        # optional rules (you can relax these)
        if TrainingSession.objects.filter(plan=plan).count() == 0:
            return Response({"detail": "Add at least one session before publishing."}, status=400)

        plan.status = "published"
        plan.save(update_fields=["status"])
        return Response({"plan_id": str(plan.plan_id), "status": plan.status}, status=200)
