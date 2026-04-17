from training.models import AIInsight, TrainingSession, WeeklyLoad


def get_upcoming_sessions(player, today, limit=3):
    return TrainingSession.objects.filter(
        plan__trainingplanplayer__player=player,
        session_date__gte=today,
    ).order_by("session_date", "start_time")[:limit]


def get_current_week_load(player, week_start):
    return WeeklyLoad.objects.filter(player=player, week_start=week_start).first()


def get_prev_week_load(player, prev_week_start):
    return WeeklyLoad.objects.filter(player=player, week_start=prev_week_start).first()


def get_today_insights(player, today):
    return AIInsight.objects.filter(player=player, date=today)
