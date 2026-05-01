from training.models import (
    PlayerCheckin,
    SessionAttendance,
    SessionLifecycle,
    TrainingPlanPlayer,
    TrainingSession,
    WeeklyLoad,
)


def get_player_plan_ids(player_user):
    return list(
        TrainingPlanPlayer.objects
        .filter(player=player_user)
        .values_list("plan_id", flat=True)
    )


def get_player_sessions(player_user, *, start_date, end_date):
    plan_ids = get_player_plan_ids(player_user)
    if not plan_ids:
        return []

    return list(
        TrainingSession.objects
        .filter(
            plan_id__in=plan_ids,
            session_date__gte=start_date,
            session_date__lte=end_date,
        )
        .select_related("lifecycle")
        .order_by("session_date", "start_time", "session_id")
    )


def get_completed_attendance_session_ids(player_user, session_ids):
    if not session_ids:
        return set()

    return set(
        SessionAttendance.objects
        .filter(
            player=player_user,
            session_id__in=session_ids,
            session__lifecycle__status=SessionLifecycle.COMPLETED,
        )
        .values_list("session_id", flat=True)
    )


def get_checkins_by_date(player_user, *, start_date, end_date):
    return {
        checkin.date: checkin
        for checkin in PlayerCheckin.objects.filter(
            player=player_user,
            date__gte=start_date,
            date__lte=end_date,
        )
    }


def get_weekly_load(player_user, *, week_start):
    return WeeklyLoad.objects.filter(player=player_user, week_start=week_start).first()
