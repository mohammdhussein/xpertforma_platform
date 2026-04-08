from django.db.models import Count, Q
from django.utils import timezone

from accounts.files import build_media_value_url
from accounts.models import CoachProfile, PlayerProfile
from accounts.statuses import (
    COACH_APPROVAL_APPROVED,
    COACH_APPROVAL_PENDING,
    normalize_coach_approval_status,
)

def _build_name_payload(user):
    return {
        "full_name": user.name,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def _build_coach_status_label(coach_profile):
    if not coach_profile.user.is_active:
        return "INACTIVE"
    return normalize_coach_approval_status(
        coach_profile.approval_status,
        default=COACH_APPROVAL_PENDING,
    )


def _humanize_player_status(login_status):
    normalized = (login_status or "").strip().lower()
    if normalized == "first_login":
        return "NEEDS_SETUP"
    if normalized in {"complete", "completed"}:
        return "ACTIVE"
    if not normalized:
        return "UNKNOWN"
    return normalized.replace("_", " ").upper()


def _build_coach_request_row(coach_profile):
    return {
        "id": coach_profile.user_id,
        "first_name": coach_profile.user.first_name,
        "last_name": coach_profile.user.last_name,
        "email": coach_profile.user.email,
        "phone_number": coach_profile.phone_number or None,
        "certificate_url": build_media_value_url(coach_profile.certificate_image),
        "status": normalize_coach_approval_status(
            coach_profile.approval_status,
            default=COACH_APPROVAL_PENDING,
        ),
        "created_at": coach_profile.user.created_at,
    }


def build_coach_requests_panel_payload():
    pending_profiles = list(
        CoachProfile.objects.filter(
            approval_status__iexact=COACH_APPROVAL_PENDING
        ).select_related("user").order_by("-user__created_at")
    )
    summary = CoachProfile.objects.aggregate(
        pending_requests=Count(
            "user_id",
            filter=Q(approval_status__iexact=COACH_APPROVAL_PENDING),
        ),
        approved_coaches=Count(
            "user_id",
            filter=Q(approval_status__iexact=COACH_APPROVAL_APPROVED),
        ),
    )

    return {
        "summary": {
            "pending_requests": summary["pending_requests"] or 0,
            "approved_coaches": summary["approved_coaches"] or 0,
        },
        "requests": [_build_coach_request_row(profile) for profile in pending_profiles],
        "last_updated": timezone.now(),
    }


def build_admin_dashboard_payload():
    recent_pending_requests = (
        CoachProfile.objects.filter(approval_status__iexact=COACH_APPROVAL_PENDING)
        .select_related("user")
        .order_by("-user__created_at")[:5]
    )

    return {
        "summary": {
            "pending_requests": CoachProfile.objects.filter(
                approval_status__iexact=COACH_APPROVAL_PENDING
            ).count(),
            "approved_coaches": CoachProfile.objects.filter(
                approval_status__iexact=COACH_APPROVAL_APPROVED
            ).count(),
            "total_coaches": CoachProfile.objects.count(),
            "total_players": PlayerProfile.objects.count(),
        },
        "recent_requests": [
            {
                "id": profile.user_id,
                **_build_name_payload(profile.user),
                "email": profile.user.email,
                "status": normalize_coach_approval_status(
                    profile.approval_status,
                    default=COACH_APPROVAL_PENDING,
                ),
                "created_at": profile.user.created_at,
            }
            for profile in recent_pending_requests
        ],
    }


def build_admin_coaches_payload():
    queryset = (
        CoachProfile.objects.select_related("user")
        .annotate(player_count=Count("user__coached_players", distinct=True))
        .order_by("-user__created_at")
    )

    rows = []
    for coach_profile in queryset:
        rows.append(
            {
                "id": coach_profile.user_id,
                **_build_name_payload(coach_profile.user),
                "email": coach_profile.user.email,
                "phone_number": coach_profile.phone_number or None,
                "status": _build_coach_status_label(coach_profile),
                "is_active": coach_profile.user.is_active,
                "joined_at": coach_profile.approved_at or coach_profile.user.created_at,
                "created_at": coach_profile.user.created_at,
                "player_count": coach_profile.player_count,
                "certificate_url": build_media_value_url(coach_profile.certificate_image),
            }
        )

    return {
        "summary": {
            "total_coaches": queryset.count(),
            "approved_coaches": queryset.filter(
                approval_status__iexact=COACH_APPROVAL_APPROVED
            ).count(),
            "active_coaches": queryset.filter(user__is_active=True).count(),
        },
        "coaches": rows,
    }


def build_admin_players_payload():
    queryset = (
        PlayerProfile.objects.select_related("user", "coach")
        .order_by("-user__created_at")
    )

    rows = []
    for player_profile in queryset:
        rows.append(
            {
                "id": player_profile.user_id,
                **_build_name_payload(player_profile.user),
                "email": player_profile.user.email,
                "assigned_coach": player_profile.coach.name if player_profile.coach_id else None,
                "status": _humanize_player_status(player_profile.login_status),
                "joined_at": player_profile.user.created_at,
                "has_coach": bool(player_profile.coach_id),
            }
        )

    return {
        "summary": {
            "total_players": queryset.count(),
            "assigned_players": queryset.filter(coach__isnull=False).count(),
            "needs_setup_players": queryset.filter(
                Q(login_status__iexact="first_login") | Q(login_status__exact="")
            ).count(),
        },
        "players": rows,
    }


def toggle_coach_active_status(coach_profile):
    user = coach_profile.user
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    return {
        "coach_id": coach_profile.user_id,
        "is_active": user.is_active,
        "status": _build_coach_status_label(coach_profile),
    }
