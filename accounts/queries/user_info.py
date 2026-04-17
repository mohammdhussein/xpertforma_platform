from accounts.files import build_media_value_url
from accounts.serializers.position import build_position_payload
from accounts.statuses import normalize_coach_approval_status

ROLE_PRIORITY = ["Admin", "Manager", "Coach", "Player", "User"]


def get_user_roles(user):
    return list(user.user_roles.select_related("role").values_list("role__role_name", flat=True))


def get_primary_role(roles):
    for role_name in ROLE_PRIORITY:
        if role_name in roles:
            return role_name
    return roles[0] if roles else "User"


def build_user_info_payload(user):
    roles = get_user_roles(user)
    primary_role = get_primary_role(roles)

    coach_data = None
    if hasattr(user, "coach_profile"):
        coach_profile = user.coach_profile
        coach_data = {
            "approval_status": normalize_coach_approval_status(coach_profile.approval_status),
            "certificate_image": build_media_value_url(coach_profile.certificate_image),
            "approved_at": coach_profile.approved_at,
            "rejection_reason": coach_profile.rejection_reason,
        }

    player_data = None
    if hasattr(user, "player_profile"):
        player_profile = user.player_profile
        player_data = {
            "position": build_position_payload(player_profile.position),
            "team_id": str(player_profile.team_id) if getattr(player_profile, "team_id", None) else None,
            "height_cm": getattr(player_profile, "height_cm", None),
            "weight_kg": getattr(player_profile, "weight_kg", None),
            "avatar_url": build_media_value_url(getattr(player_profile, "avatar", None)),
        }

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": primary_role,
        "coach": coach_data,
        "player": player_data,
    }
