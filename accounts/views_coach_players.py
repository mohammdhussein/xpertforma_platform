from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsCoach
from accounts.models import PlayerProfile
from accounts.serializers.position import build_position_payload
from training.models import TrainingPlanPlayer, TrainingSession, PlayerSessionProgress

from accounts.serializers import PlayerListResponseSerializer, PlayerTrainingProgressResponseSerializer


class CoachPlayersListAPIView(APIView):
    """
    Screen: My Players
    """
    permission_classes = [IsAuthenticated, IsCoach]

    def get(self, request):
        coach = request.user
        q = (request.query_params.get("q") or "").strip()
        tab = (request.query_params.get("tab") or "all").strip()

        base = PlayerProfile.objects.filter(coach=coach).select_related("user", "position")

        if q:
            base = base.filter(
                Q(user__name__icontains=q) |
                Q(user__email__icontains=q) |
                Q(position__name__icontains=q) |
                Q(position__code__icontains=q) |
                Q(position_label__icontains=q)
            )

        has_state = hasattr(PlayerProfile, "player_state")
        if tab != "all" and has_state:
            base = base.filter(player_state=tab)

        players = []
        for pp in base.order_by("user__name"):
            state = getattr(pp, "player_state", "active")

            players.append({
                "id": pp.user.id,
                "name": pp.user.name,
                "position": build_position_payload(pp.position, pp.position_label),
                "state": state,
            })

        payload = {"players": players}
        return Response(PlayerListResponseSerializer(payload).data)


class CoachPlayerTrainingProgressAPIView(APIView):
    """
    Screen: Player Profile -> Training Plan Progress
    """
    permission_classes = [IsAuthenticated, IsCoach]

    def get(self, request, player_id):
        coach = request.user

        pp = get_object_or_404(
            PlayerProfile.objects.select_related("user", "position"),
            user_id=player_id,
            coach=coach
        )

        player = pp.user

        assigned = (
            TrainingPlanPlayer.objects
            .filter(player=player)
            .select_related("plan")
            .order_by("-assigned_at")
        )
        plans = [a.plan for a in assigned]
        plan_ids = [p.plan_id for p in plans]

        total_sessions_map = dict(
            TrainingSession.objects
            .filter(plan_id__in=plan_ids)
            .values("plan_id")
            .annotate(c=Count("session_id"))
            .values_list("plan_id", "c")
        )

        completed_sessions_map = dict(
            PlayerSessionProgress.objects
            .filter(player=player, session__plan_id__in=plan_ids, status="completed")
            .values("session__plan_id")
            .annotate(c=Count("id"))
            .values_list("session__plan_id", "c")
        )

        today = timezone.localdate()

        plans_out = []
        for plan in plans:
            total = total_sessions_map.get(plan.plan_id, 0)
            completed = completed_sessions_map.get(plan.plan_id, 0)
            remaining = max(total - completed, 0)
            percent = int((completed / total) * 100) if total > 0 else 0

            status_label = "completed" if percent >= 100 else "active"

            plans_out.append({
                "plan_id": plan.plan_id,
                "title": plan.title,
                "started_at": plan.start_date,
                "status": status_label,
                "overall_progress_percent": percent,
                "completed_sessions": completed,
                "remaining_sessions": remaining,
            })

        payload = {
            "id": player.id,
            "name": player.name,
            "age": getattr(pp, "age", None),
            "position": build_position_payload(pp.position, pp.position_label),
            "plans": plans_out
        }

        return Response(PlayerTrainingProgressResponseSerializer(payload).data)
