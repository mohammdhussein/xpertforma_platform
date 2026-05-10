import json
import re
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.files import build_media_value_url
from accounts.models import CoachProfile, PlayerPerformanceSnapshot, PlayerProfile, Position
from accounts.queries.coach_dashboard import build_coach_dashboard_payload
from accounts.queries.coach_player_profile import get_coach_player_profile_data
from accounts.queries.coach_players_list import get_coach_players_queryset
from accounts.serializers.position import build_position_payload
from accounts.services.coach_player_attention import build_coach_player_attention_summary
from accounts.statuses import normalize_coach_approval_status, normalize_player_state
from ai_assistant.services.data_catalog import (
    DATA_ADMIN,
    DATA_ATTENDANCE,
    DATA_CHECKINS,
    DATA_COACHES,
    DATA_DASHBOARD,
    DATA_ORGANIZATIONS,
    DATA_PERFORMANCE,
    DATA_PLANS,
    DATA_PLAYERS,
    DATA_POSITIONS,
    DATA_PROFILE,
    DATA_SESSIONS,
)
from training.models import (
    PlayerCheckin,
    SessionAttendance,
    SessionLifecycle,
    TrainingPlan,
    TrainingPlanPlayer,
    TrainingSession,
)
from training.services.player_home import build_player_home
from training.services.player_performance import build_player_performance_payload
from training.statuses import to_api_training_session_type
from website.selectors.admin_panel import (
    build_admin_coaches_payload,
    build_admin_dashboard_payload,
    build_admin_players_payload,
)
from xpertforma_platform.api_values import normalize_api_value


MAX_LIST_ITEMS = 10
MAX_SESSION_ITEMS = 5
MAX_RECENT_ITEMS = 10


@dataclass
class ContextTarget:
    role: str
    target_type: str
    user: object
    selected_profile: PlayerProfile | None
    roster_profiles: list[PlayerProfile]


def build_backend_context(user, route: dict, screen: str, selected_player_id=None) -> dict:
    role = _resolve_context_role(user)
    now = timezone.now()
    today = timezone.localdate(now)
    date_window = _resolve_date_window(route.get("time_range") or {}, today=today)
    target = _resolve_target(
        user,
        role=role,
        route=route,
        selected_player_id=selected_player_id,
    )

    context = {
        "metadata": {
            "user_role": role,
            "screen": screen or "UNKNOWN",
            "route": route,
            "generated_at": today,
            "date_window": date_window,
            "data_sources_used": [],
            "missing_data_sources": [],
        }
    }

    for source in route.get("data_sources", []):
        builder = SOURCE_BUILDERS.get(source)
        if builder is None:
            context["metadata"]["missing_data_sources"].append(source)
            continue

        payload = builder(
            user=user,
            target=target,
            route=route,
            date_window=date_window,
            today=today,
        )
        context[source] = payload
        context["metadata"]["data_sources_used"].append(source)
        if _is_missing_payload(payload):
            context["metadata"]["missing_data_sources"].append(source)

    return _json_ready(context)


def context_to_compact_json(context):
    return json.dumps(context, cls=DjangoJSONEncoder, separators=(",", ":"), ensure_ascii=True)


def _resolve_context_role(user):
    if user.is_staff or user.is_superuser:
        return "ADMIN"
    if hasattr(user, "coach_profile"):
        return "COACH"
    if hasattr(user, "player_profile"):
        return "PLAYER"
    return "UNKNOWN"


def _resolve_target(user, *, role, route, selected_player_id):
    target_type = (route.get("target") or {}).get("type") or "self"
    name_hint = (route.get("target") or {}).get("name_hint")

    if role == "PLAYER":
        return ContextTarget(
            role=role,
            target_type="self",
            user=user,
            selected_profile=getattr(user, "player_profile", None),
            roster_profiles=[],
        )

    if role == "COACH":
        roster = list(get_coach_players_queryset(user))
        selected_profile = None
        if selected_player_id:
            selected_profile = next(
                (profile for profile in roster if str(profile.user_id) == str(selected_player_id)),
                None,
            )
            if selected_profile is None:
                raise PermissionDenied("You do not have access to this player.")
        elif target_type == "selected_player":
            selected_profile = _match_player_from_roster(roster, name_hint)

        return ContextTarget(
            role=role,
            target_type="selected_player" if selected_profile else ("missing_selected_player" if target_type == "selected_player" else target_type),
            user=selected_profile.user if selected_profile else user,
            selected_profile=selected_profile,
            roster_profiles=roster,
        )

    if role == "ADMIN":
        selected_profile = None
        if selected_player_id:
            selected_profile = (
                PlayerProfile.objects
                .select_related("user", "position", "coach", "team", "team__club")
                .filter(user_id=selected_player_id)
                .first()
            )
            if selected_profile is None:
                raise PermissionDenied("Selected player was not found.")
        elif target_type == "selected_player":
            selected_profile = _match_player_from_roster(
                list(
                    PlayerProfile.objects
                    .select_related("user", "position", "coach", "team", "team__club")
                ),
                name_hint,
            )
        return ContextTarget(
            role=role,
            target_type="selected_player" if selected_profile else ("missing_selected_player" if target_type == "selected_player" else target_type),
            user=selected_profile.user if selected_profile else user,
            selected_profile=selected_profile,
            roster_profiles=[],
        )

    return ContextTarget(role=role, target_type=target_type, user=user, selected_profile=None, roster_profiles=[])


def _resolve_date_window(time_range, *, today):
    range_type = time_range.get("type") or "default"
    max_days = getattr(settings, "AI_MAX_CONTEXT_DAYS", 14)

    if range_type == "latest":
        start_date = today - timedelta(days=max_days - 1)
        return {"type": "latest", "start_date": start_date, "end_date": today}
    if range_type == "today":
        return {"type": "today", "start_date": today, "end_date": today}
    if range_type == "yesterday":
        yesterday = today - timedelta(days=1)
        return {"type": "yesterday", "start_date": yesterday, "end_date": yesterday}
    if range_type == "week":
        start_date = _start_of_week_sunday(today)
        return {"type": "week", "start_date": start_date, "end_date": today}
    if range_type == "month":
        start_date = today.replace(day=1)
        return {"type": "month", "start_date": start_date, "end_date": today}

    start_date = today - timedelta(days=max_days - 1)
    return {"type": "default", "start_date": start_date, "end_date": today}


def _start_of_week_sunday(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _json_ready(value):
    return json.loads(context_to_compact_json(value))


def _is_missing_payload(payload):
    if payload is None:
        return True
    if isinstance(payload, list):
        return len(payload) == 0
    if isinstance(payload, dict):
        if payload.get("missing") is True:
            return True
        if payload.get("items") == [] and len(payload) <= 2:
            return True
    return False


def _build_profile_context(*, user, target, route, date_window, today):
    if target.target_type == "missing_selected_player":
        return {"missing": True, "reason": "No accessible selected player was provided or matched."}
    if target.role == "PLAYER":
        return {"self": _build_user_profile_payload(user, getattr(user, "player_profile", None))}
    if target.selected_profile is not None:
        return {"selected_player": _build_user_profile_payload(target.selected_profile.user, target.selected_profile)}
    if target.role == "COACH":
        return {
            "coach": _build_coach_profile_payload(user),
            "team_players_count": len(target.roster_profiles),
        }
    if target.role == "ADMIN":
        return {
            "admin": _build_basic_user_payload(user),
            "summary": build_admin_dashboard_payload().get("summary", {}),
        }
    return {"missing": True}


def _build_players_context(*, user, target, route, date_window, today):
    if target.target_type == "missing_selected_player":
        return {"missing": True, "reason": "No accessible selected player was provided or matched."}
    if target.selected_profile is not None:
        return {"selected_player": _build_player_summary(target.selected_profile, include_attention=True)}
    if target.role == "COACH":
        players = [_build_player_summary(profile, include_attention=True) for profile in target.roster_profiles[:MAX_LIST_ITEMS]]
        needs_attention = [player for player in players if player.get("needs_attention")]
        return {
            "total_players": len(target.roster_profiles),
            "players": players,
            "needs_attention": needs_attention[:MAX_LIST_ITEMS],
        }
    if target.role == "ADMIN":
        payload = build_admin_players_payload()
        return {
            "summary": payload.get("summary"),
            "players": payload.get("players", [])[:MAX_LIST_ITEMS],
        }
    return {"missing": True}


def _build_coaches_context(*, user, target, route, date_window, today):
    if target.role != "ADMIN":
        return {"missing": True}
    payload = build_admin_coaches_payload()
    return {
        "summary": payload.get("summary"),
        "coaches": payload.get("coaches", [])[:MAX_LIST_ITEMS],
    }


def _build_sessions_context(*, user, target, route, date_window, today):
    if target.target_type == "missing_selected_player":
        return {"missing": True, "reason": "No accessible selected player was provided or matched."}
    qs = _sessions_queryset_for_target(target)
    if qs is None:
        return {"missing": True}

    latest_session = (
        qs.filter(session_date__lte=today)
        .order_by("-session_date", "-start_time", "-session_id")
        .first()
    )
    counts = _build_session_count_summary(target, qs, date_window)
    if route.get("question_type") == "latest" or (route.get("time_range") or {}).get("type") == "latest":
        return {
            "latest": _serialize_session(latest_session, target),
            "counts": counts,
        }

    upcoming = list(
        qs.filter(_upcoming_session_filter(today))
        .order_by("session_date", "start_time", "session_id")[:MAX_SESSION_ITEMS]
    )
    recent = list(
        qs.filter(session_date__gte=date_window["start_date"], session_date__lte=date_window["end_date"])
        .order_by("-session_date", "-start_time", "-session_id")[:MAX_SESSION_ITEMS]
    )

    return {
        "latest": _serialize_session(latest_session, target),
        "upcoming": [_serialize_session(session, target) for session in upcoming],
        "recent": [_serialize_session(session, target) for session in recent],
        "counts": counts,
    }


def _build_attendance_context(*, user, target, route, date_window, today):
    if target.target_type == "missing_selected_player":
        return {"missing": True, "reason": "No accessible selected player was provided or matched."}
    qs = _sessions_queryset_for_target(target)
    if qs is None:
        return {"missing": True}
    summary = _build_session_count_summary(target, qs, date_window)
    missed_sessions = [
        _serialize_session(session, target)
        for session in qs.filter(
            session_date__gte=date_window["start_date"],
            session_date__lte=date_window["end_date"],
        ).order_by("-session_date", "-start_time", "-session_id")
        if _session_missed_count(session, target) > 0
    ][:MAX_SESSION_ITEMS]
    return {
        "summary": summary,
        "sessions_with_missed_players": missed_sessions,
    }


def _upcoming_session_filter(today):
    current_time = timezone.localtime(timezone.now()).time()
    return Q(session_date__gt=today) | Q(session_date=today, start_time__isnull=False, start_time__gte=current_time)


def _build_performance_context(*, user, target, route, date_window, today):
    if target.target_type == "missing_selected_player":
        return {"missing": True, "reason": "No accessible selected player was provided or matched."}
    if target.role == "PLAYER":
        return _build_player_performance_context(target.user, date_window)
    if target.selected_profile is not None:
        profile_payload = get_coach_player_profile_data(user, target.selected_profile.user_id)
        return {
            "selected_player": profile_payload.get("player"),
            "overview": _compact_player_profile_overview(profile_payload.get("overview", {})),
            "stats": profile_payload.get("stats"),
        }
    if target.role == "COACH":
        player_ids = [profile.user_id for profile in target.roster_profiles]
        return _build_team_performance_snapshot_context(player_ids)
    if target.role == "ADMIN":
        return _build_team_performance_snapshot_context(
            list(PlayerProfile.objects.values_list("user_id", flat=True)[:MAX_LIST_ITEMS])
        )
    return {"missing": True}


def _build_checkins_context(*, user, target, route, date_window, today):
    if target.target_type == "missing_selected_player":
        return {"missing": True, "reason": "No accessible selected player was provided or matched."}
    if target.role == "PLAYER" or target.selected_profile is not None:
        player_user = target.user
        checkins = list(
            PlayerCheckin.objects
            .filter(player=player_user, date__gte=date_window["start_date"], date__lte=date_window["end_date"])
            .order_by("-date", "-created_at")[:MAX_RECENT_ITEMS]
        )
        return {
            "latest": _serialize_checkin(checkins[0]) if checkins else None,
            "recent": [_serialize_checkin(checkin) for checkin in checkins],
        }

    if target.role == "COACH":
        return _build_team_readiness_context(target.roster_profiles, date_window)
    if target.role == "ADMIN":
        profiles = list(PlayerProfile.objects.select_related("user", "position")[:MAX_LIST_ITEMS])
        return _build_team_readiness_context(profiles, date_window)
    return {"missing": True}


def _build_plans_context(*, user, target, route, date_window, today):
    if target.target_type == "missing_selected_player":
        return {"missing": True, "reason": "No accessible selected player was provided or matched."}
    if target.role == "PLAYER" or target.selected_profile is not None:
        assignments = (
            TrainingPlanPlayer.objects
            .filter(player=target.user)
            .select_related("plan")
            .order_by("-assigned_at")[:MAX_SESSION_ITEMS]
        )
        return {"plans": [_serialize_plan(assignment.plan, player=target.user) for assignment in assignments]}
    if target.role == "COACH":
        plans = TrainingPlan.objects.filter(creator=user).order_by("-start_date", "-plan_id")[:MAX_SESSION_ITEMS]
        return {"plans": [_serialize_plan(plan, roster_profiles=target.roster_profiles) for plan in plans]}
    if target.role == "ADMIN":
        plans = TrainingPlan.objects.order_by("-start_date", "-plan_id")[:MAX_SESSION_ITEMS]
        return {
            "total_plans": TrainingPlan.objects.count(),
            "plans": [_serialize_plan(plan) for plan in plans],
        }
    return {"missing": True}


def _build_dashboard_context(*, user, target, route, date_window, today):
    if target.role == "PLAYER":
        payload = build_player_home(user, today)
        return {
            "readiness": payload.get("readiness"),
            "weekly_progress": payload.get("weekly_progress"),
            "upcoming_sessions": payload.get("upcoming_sessions", [])[:MAX_SESSION_ITEMS],
        }
    if target.role == "COACH":
        payload = build_coach_dashboard_payload(user, now=timezone.now())
        return {
            "overview_stats": payload.get("overview_stats"),
            "alerts": _compact_alerts(payload.get("alerts", [])[:MAX_LIST_ITEMS]),
            "alerts_total": payload.get("alerts_total"),
            "upcoming_sessions": payload.get("upcoming_sessions", [])[:MAX_SESSION_ITEMS],
        }
    if target.role == "ADMIN":
        return build_admin_dashboard_payload()
    return {"missing": True}


def _build_positions_context(*, user, target, route, date_window, today):
    positions = Position.objects.order_by("id")
    return {
        "positions": [
            {
                "id": position.id,
                "name": position.name,
                "code": position.code,
                "category": position.category,
            }
            for position in positions
        ]
    }


def _build_organizations_context(*, user, target, route, date_window, today):
    profiles = []
    if target.selected_profile is not None:
        profiles = [target.selected_profile]
    elif target.role == "PLAYER" and getattr(user, "player_profile", None):
        profiles = [user.player_profile]
    elif target.role == "COACH":
        profiles = target.roster_profiles[:MAX_LIST_ITEMS]
    elif target.role == "ADMIN":
        profiles = list(PlayerProfile.objects.select_related("user", "team", "team__club")[:MAX_LIST_ITEMS])

    return {
        "players": [
            {
                "name": profile.user.name,
                "team_name": profile.team.name if profile.team_id else None,
                "age_group": profile.team.age_group if profile.team_id else None,
                "club_name": profile.team.club.name if profile.team_id and profile.team.club_id else None,
            }
            for profile in profiles
        ]
    }


def _build_admin_context(*, user, target, route, date_window, today):
    if target.role != "ADMIN":
        return {"missing": True}
    return build_admin_dashboard_payload().get("summary", {})


SOURCE_BUILDERS = {
    DATA_PROFILE: _build_profile_context,
    DATA_PLAYERS: _build_players_context,
    DATA_COACHES: _build_coaches_context,
    DATA_SESSIONS: _build_sessions_context,
    DATA_ATTENDANCE: _build_attendance_context,
    DATA_PERFORMANCE: _build_performance_context,
    DATA_CHECKINS: _build_checkins_context,
    DATA_PLANS: _build_plans_context,
    DATA_DASHBOARD: _build_dashboard_context,
    DATA_POSITIONS: _build_positions_context,
    DATA_ORGANIZATIONS: _build_organizations_context,
    DATA_ADMIN: _build_admin_context,
}


def _build_basic_user_payload(user):
    return {
        "name": user.name or user.email,
        "email": user.email,
        "created_at": user.created_at,
        "last_seen_at": user.last_seen_at,
    }


def _build_user_profile_payload(user, profile):
    payload = _build_basic_user_payload(user)
    if profile is not None:
        payload.update(
            {
                "position": build_position_payload(profile.position),
                "avatar_url": build_media_value_url(profile.avatar),
                "height_cm": profile.height_cm,
                "weight_kg": profile.weight_kg,
                "foot": normalize_api_value(profile.foot, default=None),
                "state": normalize_player_state(profile.state, default=None),
                "expected_return_date": profile.expected_return_date,
                "team_name": profile.team.name if profile.team_id else None,
            }
        )
    return payload


def _build_coach_profile_payload(user):
    profile = getattr(user, "coach_profile", None)
    payload = _build_basic_user_payload(user)
    if profile is not None:
        payload.update(
            {
                "phone_number": profile.phone_number,
                "approval_status": normalize_coach_approval_status(profile.approval_status),
                "approved_at": profile.approved_at,
            }
        )
    return payload


def _build_player_summary(profile, *, include_attention=False):
    payload = {
        "name": profile.user.name,
        "position": build_position_payload(profile.position),
        "avatar_url": build_media_value_url(profile.avatar),
        "state": normalize_player_state(profile.state, default=None),
        "expected_return_date": profile.expected_return_date,
        "last_activity": profile.user.last_seen_at,
    }
    if include_attention:
        attention = build_coach_player_attention_summary(profile)
        payload["needs_attention"] = attention.get("needs_attention")
        payload["attention_reasons"] = [
            item.get("message")
            for item in attention.get("items", [])[:3]
            if item.get("message")
        ]
    return payload


def _sessions_queryset_for_target(target):
    if target.role == "PLAYER" or target.selected_profile is not None:
        return (
            TrainingSession.objects
            .filter(plan__trainingplanplayer__player=target.user)
            .select_related("plan", "lifecycle")
            .distinct()
        )
    if target.role == "COACH":
        player_ids = [profile.user_id for profile in target.roster_profiles]
        return (
            TrainingSession.objects
            .filter(plan__trainingplanplayer__player_id__in=player_ids)
            .select_related("plan", "lifecycle")
            .distinct()
        )
    if target.role == "ADMIN":
        return TrainingSession.objects.select_related("plan", "lifecycle").distinct()
    return None


def _build_session_count_summary(target, sessions_qs, date_window):
    sessions = list(
        sessions_qs
        .filter(session_date__gte=date_window["start_date"], session_date__lte=date_window["end_date"])
        .values("session_id", "plan_id")
    )
    if not sessions:
        return {
            "planned": 0,
            "attended": 0,
            "missed": 0,
            "attendance_rate": None,
            "window_days": _window_days(date_window),
        }

    if target.role == "PLAYER" or target.selected_profile is not None:
        session_ids = [session["session_id"] for session in sessions]
        attended = SessionAttendance.objects.filter(
            player=target.user,
            session_id__in=session_ids,
            status__in=[SessionAttendance.PRESENT, SessionAttendance.LATE],
        ).count()
        planned = len(session_ids)
        return {
            "planned": planned,
            "attended": attended,
            "completed": attended,
            "missed": max(planned - attended, 0),
            "attendance_rate": _percentage(attended, planned),
            "window_days": _window_days(date_window),
        }

    if target.role == "COACH":
        roster_ids = {profile.user_id for profile in target.roster_profiles}
    else:
        roster_ids = set(PlayerProfile.objects.values_list("user_id", flat=True))

    expected_player_sessions = 0
    attended_player_sessions = 0
    missed_player_sessions = 0
    sessions_with_missed_players = 0
    expected_by_plan = _expected_player_ids_by_plan(sessions, roster_ids)

    for session in sessions:
        expected_ids = expected_by_plan.get(session["plan_id"], set())
        attended_ids = set(
            SessionAttendance.objects
            .filter(
                session_id=session["session_id"],
                player_id__in=expected_ids,
                status__in=[SessionAttendance.PRESENT, SessionAttendance.LATE],
            )
            .values_list("player_id", flat=True)
        )
        missed = max(len(expected_ids) - len(attended_ids), 0)
        expected_player_sessions += len(expected_ids)
        attended_player_sessions += len(attended_ids)
        missed_player_sessions += missed
        if missed:
            sessions_with_missed_players += 1

    return {
        "sessions": len(sessions),
        "expected_player_sessions": expected_player_sessions,
        "attended_player_sessions": attended_player_sessions,
        "missed_player_sessions": missed_player_sessions,
        "sessions_with_missed_players": sessions_with_missed_players,
        "attendance_rate": _percentage(attended_player_sessions, expected_player_sessions),
        "window_days": _window_days(date_window),
    }


def _serialize_session(session, target):
    if session is None:
        return None
    payload = {
        "title": session.title or session.plan.title,
        "plan_title": session.plan.title,
        "session_date": session.session_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "intensity": normalize_api_value(session.intensity),
        "session_type": to_api_training_session_type(session.session_type),
        "location": session.location,
        "status": _session_status(session),
    }

    if target.role == "PLAYER" or target.selected_profile is not None:
        attendance = SessionAttendance.objects.filter(session=session, player=target.user).first()
        payload["attendance_status"] = normalize_api_value(attendance.status if attendance else "NOT_MARKED")
    elif target.role in {"COACH", "ADMIN"}:
        expected_ids = _session_expected_player_ids(session, target)
        attended_ids = set(
            SessionAttendance.objects
            .filter(
                session=session,
                player_id__in=expected_ids,
                status__in=[SessionAttendance.PRESENT, SessionAttendance.LATE],
            )
            .values_list("player_id", flat=True)
        )
        missed_ids = expected_ids - attended_ids
        payload["attendance"] = {
            "expected_players": len(expected_ids),
            "attended_players": len(attended_ids),
            "missed_players": len(missed_ids),
            "missed_player_names": _player_name_rows(missed_ids),
        }
    return payload


def _session_status(session):
    lifecycle = _get_session_lifecycle(session)
    return normalize_api_value(lifecycle.status if lifecycle else SessionLifecycle.NOT_STARTED)


def _get_session_lifecycle(session):
    try:
        return session.lifecycle
    except ObjectDoesNotExist:
        return None


def _session_missed_count(session, target):
    if target.role == "PLAYER" or target.selected_profile is not None:
        return 0 if SessionAttendance.objects.filter(session=session, player=target.user).exists() else 1
    expected_ids = _session_expected_player_ids(session, target)
    attended_ids = set(
        SessionAttendance.objects
        .filter(session=session, player_id__in=expected_ids, status__in=[SessionAttendance.PRESENT, SessionAttendance.LATE])
        .values_list("player_id", flat=True)
    )
    return max(len(expected_ids) - len(attended_ids), 0)


def _session_expected_player_ids(session, target):
    if target.role == "COACH":
        roster_ids = {profile.user_id for profile in target.roster_profiles}
        return set(
            TrainingPlanPlayer.objects
            .filter(plan=session.plan, player_id__in=roster_ids)
            .values_list("player_id", flat=True)
        )
    if target.role == "ADMIN":
        return set(TrainingPlanPlayer.objects.filter(plan=session.plan).values_list("player_id", flat=True))
    return set()


def _expected_player_ids_by_plan(sessions, roster_ids):
    plan_ids = {session["plan_id"] for session in sessions}
    rows = (
        TrainingPlanPlayer.objects
        .filter(plan_id__in=plan_ids, player_id__in=roster_ids)
        .values("plan_id", "player_id")
    )
    expected = {plan_id: set() for plan_id in plan_ids}
    for row in rows:
        expected[row["plan_id"]].add(row["player_id"])
    return expected


def _build_player_performance_context(player_user, date_window):
    payload = build_player_performance_payload(
        player_user,
        start_date_str=date_window["start_date"].isoformat(),
        end_date_str=date_window["end_date"].isoformat(),
    )
    days = payload.get("days", [])
    signal_days = [day for day in days if _performance_day_has_signal(day)]
    summary = _summarize_performance_days(days)
    summary["readiness_checkins_logged"] = PlayerCheckin.objects.filter(
        player=player_user,
        date__gte=date_window["start_date"],
        date__lte=date_window["end_date"],
    ).count()
    return {
        "summary": summary,
        "latest_day": signal_days[-1] if signal_days else None,
        "recent_days": signal_days[-MAX_RECENT_ITEMS:],
    }


def _summarize_performance_days(days):
    planned = sum((day.get("sessions") or {}).get("planned", 0) for day in days)
    completed = sum((day.get("sessions") or {}).get("completed", 0) for day in days)
    scores = [day.get("score") for day in days if day.get("score") is not None]
    recovery = [(day.get("recovery") or {}).get("percentage") for day in days]
    recovery = [value for value in recovery if value is not None]
    return {
        "sessions_planned": planned,
        "sessions_completed": completed,
        "completion_rate": _percentage(completed, planned),
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "average_recovery": round(sum(recovery) / len(recovery)) if recovery else None,
    }


def _performance_day_has_signal(day):
    sessions = day.get("sessions") or {}
    recovery = day.get("recovery") or {}
    return bool(day.get("score") or sessions.get("planned") or sessions.get("completed") or recovery.get("percentage"))


def _compact_player_profile_overview(overview):
    return {
        "summary": overview.get("summary"),
        "keyMetrics": overview.get("keyMetrics"),
        "recentActivity": (overview.get("recentActivity") or [])[:MAX_SESSION_ITEMS],
    }


def _build_team_performance_snapshot_context(player_ids):
    snapshots = (
        PlayerPerformanceSnapshot.objects
        .filter(player_id__in=player_ids)
        .select_related("player")
        .order_by("-recorded_at", "-id")[:MAX_LIST_ITEMS]
    )
    return {
        "latest_snapshots": [
            {
                "player_name": snapshot.player.name,
                "recorded_at": snapshot.recorded_at,
                "speed": snapshot.speed,
                "stamina": snapshot.stamina,
                "strength": snapshot.strength,
                "skills": snapshot.skills,
                "focus_area": snapshot.focus_area_override or None,
            }
            for snapshot in snapshots
        ]
    }


def _serialize_checkin(checkin):
    if checkin is None:
        return None
    return {
        "date": checkin.date,
        "readiness_score": checkin.readiness_score,
        "sleep_hours": checkin.sleep_hours,
        "sleep_quality": normalize_api_value(checkin.sleep_quality),
        "mood": checkin.mood,
        "sore_zones": checkin.sore_zones,
    }


def _build_team_readiness_context(profiles, date_window):
    rows = []
    for profile in profiles:
        checkin = (
            PlayerCheckin.objects
            .filter(player=profile.user, date__gte=date_window["start_date"], date__lte=date_window["end_date"])
            .order_by("-date", "-created_at")
            .first()
        )
        if checkin is None:
            continue
        rows.append(
            {
                "player": _build_player_summary(profile),
                "latest_checkin": _serialize_checkin(checkin),
            }
        )
    rows.sort(key=lambda row: (row["latest_checkin"]["readiness_score"], row["player"]["name"].lower()), reverse=True)
    return {
        "players_with_checkins": len(rows),
        "best_readiness": rows[0] if rows else None,
        "lowest_readiness": rows[-1] if rows else None,
        "players": rows[:MAX_LIST_ITEMS],
    }


def _serialize_plan(plan, *, player=None, roster_profiles=None):
    sessions_count = TrainingSession.objects.filter(plan=plan).count()
    payload = {
        "title": plan.title,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "status": normalize_api_value(plan.status),
        "sessions_count": sessions_count,
    }
    if player is not None:
        payload["assigned_to_user"] = True
    if roster_profiles is not None:
        roster_ids = {profile.user_id for profile in roster_profiles}
        payload["assigned_players_count"] = (
            TrainingPlanPlayer.objects
            .filter(plan=plan, player_id__in=roster_ids)
            .count()
        )
    else:
        payload["assigned_players_count"] = TrainingPlanPlayer.objects.filter(plan=plan).count()
    return payload


def _compact_alerts(alerts):
    compact = []
    for alert in alerts:
        compact.append(
            {
                "severity": alert.get("severity"),
                "alert_type": alert.get("alert_type"),
                "title": alert.get("title"),
                "description": alert.get("description"),
                "related_players": [
                    {
                        "name": player.get("name"),
                        "position": player.get("position"),
                        "avatar_url": player.get("avatar_url"),
                    }
                    for player in (alert.get("related_players") or [])[:MAX_SESSION_ITEMS]
                ],
            }
        )
    return compact


def _player_name_rows(player_ids):
    if not player_ids:
        return []
    profiles = (
        PlayerProfile.objects
        .filter(user_id__in=player_ids)
        .select_related("user", "position")
        .order_by("user__first_name", "user__last_name", "user__email")
    )
    return [_build_player_summary(profile) for profile in profiles[:MAX_SESSION_ITEMS]]


def _percentage(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator * 100)


def _window_days(date_window):
    return (date_window["end_date"] - date_window["start_date"]).days + 1


def _match_player_from_roster(roster, name_hint):
    if not name_hint:
        return None
    hint_tokens = set(_tokenize(name_hint))
    best = None
    best_score = 0
    tied = False
    for profile in roster:
        name_tokens = set(_tokenize(profile.user.name))
        score = len(hint_tokens & name_tokens)
        if score > best_score:
            best = profile
            best_score = score
            tied = False
        elif score and score == best_score:
            tied = True
    if tied or best_score == 0:
        return None
    return best


def _tokenize(value):
    return re.findall(r"[a-z0-9]+", str(value or "").lower())
