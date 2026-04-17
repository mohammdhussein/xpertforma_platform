from django.db.models import Count

from accounts.serializers.position import build_position_payload
from training.models import TrainingPlan, TrainingPlanPlayer
from training.serializers.training_plans import TrainingPlanDetailSerializer
from training.statuses import to_api_training_session_type


def get_coach_training_plans_queryset(coach_user):
    return (
        TrainingPlan.objects.filter(creator=coach_user)
        .annotate(
            total_sessions=Count("sessions", distinct=True),
            assigned_players=Count("trainingplanplayer", distinct=True),
        )
        .order_by("-start_date", "-end_date")
    )


def _build_time_range(start_time, end_time):
    if not start_time or not end_time:
        return ""
    return f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"


def _day_label(value):
    return f"{value.strftime('%A')}, {value.strftime('%b')} {value.day}"


def build_training_plan_screen_payload(plan, request):
    assigned_rows = (
        TrainingPlanPlayer.objects.filter(plan=plan)
        .select_related("player", "player__player_profile", "player__player_profile__position")
        .order_by("player__first_name", "player__last_name", "player__email")
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
                "position": build_position_payload(getattr(player_profile, "position", None)),
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
                "session_type": to_api_training_session_type(session.session_type),
                "start_time": session.start_time,
                "end_time": session.end_time,
                "time_range": _build_time_range(session.start_time, session.end_time),
            }
        )

    return {
        **TrainingPlanDetailSerializer(plan).data,
        "assigned_players": assigned_players,
        "training_sessions": grouped_sessions,
    }

