from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from accounts.models import PlayerProfile
from accounts.serializers.position import build_position_payload
from training.models import PlayerSessionProgress, TrainingPlanPlayer, TrainingSession
from training.statuses import COMPLETED_PLAYER_SESSION_STATUSES


def get_coach_players_queryset(coach_user):
    return PlayerProfile.objects.filter(coach=coach_user).select_related("user", "position")


def build_coach_players_list_payload(coach_user, *, query="", tab="all"):
    queryset = get_coach_players_queryset(coach_user)

    if query:
        queryset = queryset.filter(
            Q(user__name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(position__name__icontains=query)
            | Q(position__code__icontains=query)
            | Q(position_label__icontains=query)
        )

    if tab != "all" and hasattr(PlayerProfile, "player_state"):
        queryset = queryset.filter(player_state=tab)

    players = []
    for profile in queryset.order_by("user__name"):
        players.append(
            {
                "id": profile.user.id,
                "name": profile.user.name,
                "position": build_position_payload(profile.position, profile.position_label),
                "state": getattr(profile, "player_state", "active"),
            }
        )

    return {"players": players}


def build_coach_player_training_progress_payload(coach_user, player_id):
    player_profile = get_object_or_404(
        get_coach_players_queryset(coach_user),
        user_id=player_id,
    )
    player = player_profile.user

    assignments = (
        TrainingPlanPlayer.objects.filter(player=player).select_related("plan").order_by("-assigned_at")
    )
    plans = [assignment.plan for assignment in assignments]
    plan_ids = [plan.plan_id for plan in plans]

    total_sessions_map = dict(
        TrainingSession.objects.filter(plan_id__in=plan_ids)
        .values("plan_id")
        .annotate(c=Count("session_id"))
        .values_list("plan_id", "c")
    )
    completed_sessions_map = dict(
        PlayerSessionProgress.objects.filter(
            player=player,
            session__plan_id__in=plan_ids,
            status__in=COMPLETED_PLAYER_SESSION_STATUSES,
        )
        .values("session__plan_id")
        .annotate(c=Count("id"))
        .values_list("session__plan_id", "c")
    )

    plans_out = []
    for plan in plans:
        total = total_sessions_map.get(plan.plan_id, 0)
        completed = completed_sessions_map.get(plan.plan_id, 0)
        remaining = max(total - completed, 0)
        percent = int((completed / total) * 100) if total > 0 else 0

        plans_out.append(
            {
                "plan_id": plan.plan_id,
                "title": plan.title,
                "started_at": plan.start_date,
                "status": "completed" if percent >= 100 else "active",
                "overall_progress_percent": percent,
                "completed_sessions": completed,
                "remaining_sessions": remaining,
            }
        )

    return {
        "id": player.id,
        "name": player.name,
        "age": getattr(player_profile, "age", None),
        "position": build_position_payload(player_profile.position, player_profile.position_label),
        "plans": plans_out,
    }

