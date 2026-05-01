from datetime import timedelta

from accounts.files import build_media_value_url
from accounts.serializers.position import build_position_payload
from accounts.statuses import PLAYER_STATE_INJURED
from training.models import (
    PlayerCheckin,
    SessionAttendance,
    SessionLifecycle,
    TrainingPlanPlayer,
)

FATIGUE_READINESS_THRESHOLD = 30
FATIGUE_CRITICAL_READINESS_THRESHOLD = 20
FATIGUE_CONSECUTIVE_DAYS = 3
FATIGUE_RECENT_DAYS = 1
ATTENDANCE_RATE_THRESHOLD = 0.70
ATTENDANCE_LOOKBACK_DAYS = 30
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
    alerts.extend(_low_attendance_alerts(player_profiles, plan_ids, now))
    alerts.extend(_plan_updated_alerts(plan_ids, coach, now))

    alerts.sort(key=lambda a: a["occurred_at"], reverse=True)
    alerts.sort(key=lambda a: SEVERITY_ORDER[a["severity"]])

    total = len(alerts)
    return (alerts[:limit] if limit is not None else alerts), total


def _injury_risk_alerts(player_profiles, now):
    alerts = []
    today_str = now.date().strftime("%Y%m%d")
    injured_profiles = [pp for pp in player_profiles if pp.state == PLAYER_STATE_INJURED]

    if injured_profiles:
        player_count = len(injured_profiles)
        alerts.append({
            "id": f"PLAYER_INJURED:{today_str}",
            "severity": "CRITICAL",
            "alert_type": "PLAYER_INJURED",
            "title": "Injured Players" if player_count > 1 else "Injured Player",
            "description": (
                f"{player_count} players are currently marked as injured."
                if player_count > 1
                else "1 player is currently marked as injured."
            ),
            "related_players": [_player_item(pp) for pp in injured_profiles],
            "related_session": None,
            "related_plan": None,
            "occurred_at": now.isoformat(),
        })

    for pp in player_profiles:
        if pp.state == PLAYER_STATE_INJURED:
            continue

        checkins = list(
            PlayerCheckin.objects.filter(player=pp.user)
            .order_by("-date")[:FATIGUE_CONSECUTIVE_DAYS]
        )
        if len(checkins) < FATIGUE_CONSECUTIVE_DAYS:
            continue
        newest_checkin = checkins[0]
        if now.date() - newest_checkin.date > timedelta(days=FATIGUE_RECENT_DAYS):
            continue
        if not all(c.readiness_score < FATIGUE_READINESS_THRESHOLD for c in checkins):
            continue
        dates = [c.date for c in checkins]
        if not all((dates[i] - dates[i + 1]).days == 1 for i in range(len(dates) - 1)):
            continue

        is_critical = (
            all(c.readiness_score < FATIGUE_CRITICAL_READINESS_THRESHOLD for c in checkins)
            or any(c.sore_zones for c in checkins)
        )
        alerts.append({
            "id": f"FATIGUE_RISK:{pp.user_id}:{today_str}",
            "severity": "CRITICAL" if is_critical else "WARNING",
            "alert_type": "FATIGUE_RISK",
            "title": "Fatigue Risk",
            "description": f"High fatigue index for {FATIGUE_CONSECUTIVE_DAYS} consecutive days. Rest recommended.",
            "related_players": [_player_item(pp)],
            "related_session": None,
            "related_plan": None,
            "occurred_at": newest_checkin.created_at.isoformat(),
        })

    return alerts


def _low_attendance_alerts(player_profiles, plan_ids, now):
    alerts = []
    player_ids = [pp.user_id for pp in player_profiles]
    profile_by_player_id = {pp.user_id: pp for pp in player_profiles}
    cutoff = now - timedelta(days=ATTENDANCE_LOOKBACK_DAYS)
    lifecycles = list(
        SessionLifecycle.objects.filter(
            session__plan_id__in=plan_ids,
            status="COMPLETED",
            ended_at__gte=cutoff,
            ended_at__isnull=False,
        )
        .select_related("session__plan")
        .order_by("-ended_at")
    )

    for lc in lifecycles:
        session = lc.session
        expected_player_ids = list(
            TrainingPlanPlayer.objects.filter(
                plan=session.plan,
                player_id__in=player_ids,
            ).values_list("player_id", flat=True)
        )
        expected = len(expected_player_ids)
        if expected == 0:
            continue
        attended_player_ids = set(
            SessionAttendance.objects.filter(
                session=session,
                player_id__in=player_ids,
                status__in=["PRESENT", "LATE"],
            ).values_list("player_id", flat=True)
        )
        attended = len(attended_player_ids)
        if attended / expected >= ATTENDANCE_RATE_THRESHOLD:
            continue

        absent_profiles = [
            profile_by_player_id[player_id]
            for player_id in expected_player_ids
            if player_id not in attended_player_ids and player_id in profile_by_player_id
        ]
        date_str = lc.ended_at.date().strftime("%Y%m%d")
        session_label = session.title or session.plan.title
        alerts.append({
            "id": f"LOW_ATTENDANCE:{session.session_id}:{date_str}",
            "severity": "WARNING",
            "alert_type": "LOW_ATTENDANCE",
            "title": f"Low Attendance — {session_label}",
            "description": f"{attended} of {expected} expected players attended.",
            "related_players": [_player_item(pp) for pp in absent_profiles],
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
        "position": build_position_payload(pp.position),
        "avatar_url": build_media_value_url(pp.avatar),
    }
