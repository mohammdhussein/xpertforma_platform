from zoneinfo import ZoneInfo

from django.conf import settings
from datetime import timedelta, datetime
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.files import build_media_value_url
from accounts.permissions import IsApprovedCoach
from accounts.models import PlayerProfile
from accounts.serializers.position import build_position_payload
from training.models import TrainingPlanPlayer, TrainingSession
from training.statuses import to_api_training_session_type
from accounts.utils import duration_minutes
from accounts.serializers.coach_dashboard import CoachDashboardSerializer

UPCOMING_SESSIONS_LIMIT = 3


def _start_of_week_sunday(date_value):
    return date_value - timedelta(days=(date_value.weekday() + 1) % 7)


def _dashboard_now():
    dashboard_timezone = ZoneInfo(getattr(settings, "APP_LOCAL_TIME_ZONE", "Asia/Jerusalem"))
    return timezone.localtime(timezone.now(), dashboard_timezone)


class CoachDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedCoach]

    def get(self, request):
        coach = request.user
        dashboard_now = _dashboard_now()
        today = dashboard_now.date()
        current_time = dashboard_now.time()

        # week range (Sun..Sat)
        week_start = _start_of_week_sunday(today)
        week_end = week_start + timedelta(days=7)

        # month range
        month_start = today.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)

        # total players (coach -> players)
        players_qs = PlayerProfile.objects.filter(coach=coach).select_related("user", "position")
        total_players = players_qs.count()

        # get all assigned plans for coach players (so upcoming sessions can include those players)
        player_ids = list(players_qs.values_list("user_id", flat=True))

        assigned = TrainingPlanPlayer.objects.filter(player_id__in=player_ids).select_related("plan")
        plan_ids = list(assigned.values_list("plan_id", flat=True).distinct())

        # sessions this week/month (based on those plans)
        sessions_week = TrainingSession.objects.filter(
            plan_id__in=plan_ids,
            session_date__gte=week_start,
            session_date__lt=week_end
        ).count()

        sessions_month = TrainingSession.objects.filter(
            plan_id__in=plan_ids,
            session_date__gte=month_start,
            session_date__lt=next_month
        ).count()

        # My players preview list (top 4)
        # last_activity: latest PlayerSessionProgress.updated_at if you have it
        # If not, return null.
        my_players = []
        for pp in players_qs.order_by("user__first_name", "user__last_name", "user__email")[:4]:
            my_players.append({
                "id": pp.user.id,
                "name": pp.user.name,
                "position": build_position_payload(pp.position),
                "last_activity": pp.user.last_seen_at,
                "avatar_url": build_media_value_url(pp.avatar),
            })

            # upcoming sessions (next 7 days)

        upcoming = (
            TrainingSession.objects
            .filter(plan_id__in=plan_ids, session_date__lte=today + timedelta(days=7))
            .filter(
                Q(session_date__gt=today)
                | Q(session_date=today, start_time__gte=current_time)
            )
            .select_related("plan")
            .order_by("session_date", "start_time")[:UPCOMING_SESSIONS_LIMIT]
        )

        # players_count per session:
        # since sessions belong to plan, count assigned players to that plan
        players_count_map = dict(
            TrainingPlanPlayer.objects
            .filter(plan_id__in=[s.plan_id for s in upcoming], player_id__in=player_ids)
            .values("plan_id")
            .annotate(c=Count("player_id", distinct=True))
            .values_list("plan_id", "c")
        )

        upcoming_out = []
        for s in upcoming:
            upcoming_out.append({
                "session_id": s.session_id,
                "plan_id": s.plan_id,
                "title": (s.title or s.plan.title),
                "session_date": s.session_date,
                "start_time": s.start_time,
                "session_type": to_api_training_session_type(s.session_type),
                "players_count": players_count_map.get(s.plan_id, 0),
                "duration_min": duration_minutes(s.start_time, s.end_time),
            })

        payload = {
            "stats": {
                "total_players": total_players,
                "sessions_this_week": sessions_week,
                "sessions_this_month": sessions_month,
            },
            "my_players": my_players,
            "upcoming_sessions": upcoming_out,
        }

        return Response(CoachDashboardSerializer(payload).data)
