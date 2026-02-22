from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsCoach
from accounts.models import PlayerProfile
from training.models import TrainingPlanPlayer, TrainingSession, PlayerSessionProgress

from accounts.serializers import PlayerListResponseSerializer, PlayerTrainingProgressResponseSerializer


def _paginate(qs, page, page_size):
    page = max(int(page), 1)
    page_size = min(max(int(page_size), 1), 50)
    start = (page - 1) * page_size
    end = start + page_size
    return qs[start:end], page, page_size


class CoachPlayersListAPIView(APIView):
    """
    Screen: My Players
    """
    permission_classes = [IsAuthenticated, IsCoach]

    def get(self, request):
        coach = request.user
        q = (request.query_params.get("q") or "").strip()
        tab = (request.query_params.get("tab") or "all").strip()
        page = request.query_params.get("page") or 1
        page_size = request.query_params.get("page_size") or 10

        base = PlayerProfile.objects.filter(coach=coach).select_related("user")

        if q:
            base = base.filter(
                Q(user__name__icontains=q) |
                Q(user__email__icontains=q) |
                Q(position__icontains=q)
            )

        has_state = hasattr(PlayerProfile, "player_state")
        if tab != "all" and has_state:
            base = base.filter(player_state=tab)

        counts = {"all": PlayerProfile.objects.filter(coach=coach).count()}
        if has_state:
            counts["active"] = PlayerProfile.objects.filter(coach=coach, player_state="active").count()
            counts["needs_review"] = PlayerProfile.objects.filter(coach=coach, player_state="needs_review").count()
            counts["injured"] = PlayerProfile.objects.filter(coach=coach, player_state="injured").count()
        else:
            counts.update({"active": 0, "needs_review": 0, "injured": 0})

        base = base.order_by("user__name")
        page_qs, page, page_size = _paginate(base, page, page_size)

        player_ids = [pp.user_id for pp in page_qs]

        # collect assigned plan titles per player
        tpp = (
            TrainingPlanPlayer.objects
            .filter(player_id__in=player_ids)
            .select_related("plan")
            .order_by("-assigned_at")
        )

        plans_by_player = {}
        for row in tpp:
            plans_by_player.setdefault(row.player_id, [])
            if row.plan.title not in plans_by_player[row.player_id]:
                plans_by_player[row.player_id].append(row.plan.title)

        results = []
        for pp in page_qs:
            titles = plans_by_player.get(pp.user_id, [])
            first_two = titles[:2]
            more = max(len(titles) - 2, 0)
            state = getattr(pp, "player_state", "active")

            results.append({
                "id": pp.user.id,
                "name": pp.user.name,
                "position": pp.position or "",
                "state": state,
                "plan_chips": first_two,
                "more_plans_count": more,
            })

        payload = {"counts": counts, "results": results, "page": page, "page_size": page_size}
        return Response(PlayerListResponseSerializer(payload).data)


class CoachPlayerTrainingProgressAPIView(APIView):
    """
    Screen: Player Profile -> Training Plan Progress
    """
    permission_classes = [IsAuthenticated, IsCoach]

    def get(self, request, player_id):
        coach = request.user

        pp = get_object_or_404(
            PlayerProfile.objects.select_related("user"),
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
            "player": {
                "id": player.id,
                "name": player.name,
                "age": getattr(pp, "age", None),
                "position": pp.position or "",
            },
            "plans": plans_out
        }

        return Response(PlayerTrainingProgressResponseSerializer(payload).data)
