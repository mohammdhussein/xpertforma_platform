from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from accounts.files import build_media_value_url
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
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(position__name__icontains=query)
            | Q(position__code__icontains=query)
        )

    if tab != "all":
        queryset = queryset.filter(state=tab)

    players = []
    for profile in queryset.order_by("user__first_name", "user__last_name", "user__email"):
        players.append(
            {
                "id": profile.user.id,
                "name": profile.user.name,
                "position": build_position_payload(profile.position),
                "state": profile.state,
                "avatar_url": build_media_value_url(profile.avatar),
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
        "age": player_profile.age,
        "phone": player_profile.phone,
        "foot": player_profile.foot,
        "state": player_profile.state,
        "position": build_position_payload(player_profile.position),
        "plans": plans_out,
    }

