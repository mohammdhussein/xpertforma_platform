from datetime import timedelta

from accounts.files import build_media_value_url
from training.models import (
    PlayerCheckin,
    SessionAttendance,
    SessionLifecycle,
    TrainingPlanPlayer,
)

FATIGUE_READINESS_THRESHOLD = 30
FATIGUE_CONSECUTIVE_DAYS = 3
ATTENDANCE_RATE_THRESHOLD = 0.70
PLAN_ASSIGNMENT_LOOKBACK_HOURS = 24
SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def build_coach_alerts(coach, *, limit=3, now) -> tuple:
    """Return (top_alerts, total_count). limit=None returns all."""
    from accounts.models import PlayerProfile

    player_profiles = list(
        PlayerProfile.objects.filter(coach=coach).select_related("user", "position")
    )
    player_ids = [pp.user_id for pp in player_profiles]
    plan_ids = list(
        TrainingPlanPlayer.objects.filter(player_id__in=player_ids)
        .values_list("plan_id", flat=True)
        .distinct()
    )

    alerts = []
    alerts.extend(_injury_risk_alerts(player_profiles, now))
    alerts.extend(_low_attendance_alerts(player_ids, plan_ids, now))
    alerts.extend(_plan_updated_alerts(plan_ids, coach, now))

    alerts.sort(key=lambda a: a["occurred_at"], reverse=True)
    alerts.sort(key=lambda a: SEVERITY_ORDER[a["severity"]])

    total = len(alerts)
    return (alerts[:limit] if limit is not None else alerts), total


def _injury_risk_alerts(player_profiles, now):
    alerts = []
    today_str = now.date().strftime("%Y%m%d")

    for pp in player_profiles:
        if pp.state == "INJURED":
            alerts.append({
                "id": f"INJURY_RISK:{pp.user_id}:{today_str}",
                "severity": "CRITICAL",
                "alert_type": "INJURY_RISK",
                "title": f"Injury Risk",
                "description": "Player is currently marked as injured.",
                "related_players": [_player_item(pp)],
                "related_session": None,
                "related_plan": None,
                "occurred_at": now.isoformat(),
            })
            continue

        checkins = list(
            PlayerCheckin.objects.filter(player=pp.user)
            .order_by("-date")[:FATIGUE_CONSECUTIVE_DAYS]
        )
        if len(checkins) < FATIGUE_CONSECUTIVE_DAYS:
            continue
        if not all(c.readiness_score < FATIGUE_READINESS_THRESHOLD for c in checkins):
            continue
        dates = [c.date for c in checkins]
        if not all((dates[i] - dates[i + 1]).days == 1 for i in range(len(dates) - 1)):
            continue

        alerts.append({
            "id": f"INJURY_RISK:{pp.user_id}:{today_str}",
            "severity": "CRITICAL",
            "alert_type": "INJURY_RISK",
            "title": f"Injury Risk",
            "description": f"High fatigue index for {FATIGUE_CONSECUTIVE_DAYS} consecutive days. Rest recommended.",
            "related_players": [_player_item(pp)],
            "related_session": None,
            "related_plan": None,
            "occurred_at": checkins[-1].created_at.isoformat(),
        })

    return alerts


def _low_attendance_alerts(player_ids, plan_ids, now):
    alerts = []
    lifecycles = list(
        SessionLifecycle.objects.filter(
            session__plan_id__in=plan_ids,
            status="COMPLETED",
            ended_at__isnull=False,
        )
        .select_related("session__plan")
        .order_by("-ended_at")[:10]
    )

    for lc in lifecycles:
        session = lc.session
        expected = TrainingPlanPlayer.objects.filter(
            plan=session.plan, player_id__in=player_ids
        ).count()
        if expected == 0:
            continue
        attended = SessionAttendance.objects.filter(
            session=session,
            player_id__in=player_ids,
            status__in=["PRESENT", "LATE"],
        ).count()
        if attended / expected >= ATTENDANCE_RATE_THRESHOLD:
            continue

        date_str = lc.ended_at.date().strftime("%Y%m%d")
        session_label = session.title or session.plan.title
        alerts.append({
            "id": f"LOW_ATTENDANCE:{session.session_id}:{date_str}",
            "severity": "WARNING",
            "alert_type": "LOW_ATTENDANCE",
            "title": f"Low Attendance — {session_label}",
            "description": f"{attended} of {expected} expected players attended.",
            "related_players": [],
            "related_session": {
                "session_id": session.session_id,
                "plan_id": session.plan_id,
                "title": session.title or session.plan.title,
                "session_date": session.session_date,
                "start_time": session.start_time,
            },
            "related_plan": None,
            "occurred_at": lc.ended_at.isoformat(),
        })

    return alerts


def _plan_updated_alerts(plan_ids, coach, now):
    cutoff = now - timedelta(hours=PLAN_ASSIGNMENT_LOOKBACK_HOURS)
    assignments = list(
        TrainingPlanPlayer.objects.filter(
            plan_id__in=plan_ids,
            assigned_at__gte=cutoff,
        )
        .exclude(assigned_by=coach)
        .select_related("plan")
        .order_by("-assigned_at")
    )

    today_str = now.date().strftime("%Y%m%d")
    seen_plans = set()
    alerts = []
    for assignment in assignments:
        plan = assignment.plan
        if plan.plan_id in seen_plans:
            continue
        seen_plans.add(plan.plan_id)
        alerts.append({
            "id": f"PLAN_UPDATED:{plan.plan_id}:{today_str}",
            "severity": "INFO",
            "alert_type": "PLAN_UPDATED",
            "title": f"Plan Updated — {plan.title}",
            "description": "A player was recently assigned to this plan by another user.",
            "related_players": [],
            "related_session": None,
            "related_plan": {
                "plan_id": plan.plan_id,
                "title": plan.title,
            },
            "occurred_at": assignment.assigned_at.isoformat(),
        })

    return alerts


def _player_item(pp):
    return {
        "id": pp.user_id,
        "name": pp.user.name,
        "avatar_url": build_media_value_url(pp.avatar),
    }
