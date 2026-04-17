from django.db.models import Q
from rest_framework.exceptions import ParseError

from accounts.files import build_media_value_url
from accounts.models import PlayerProfile
from accounts.serializers.position import build_position_payload
from accounts.statuses import normalize_player_state, parse_player_state_api_value
from xpertforma_platform.api_values import normalize_api_value


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

    normalized_tab = normalize_api_value(tab, default="ALL")
    if tab and tab != normalized_tab:
        raise ParseError(detail="Invalid tab. Use uppercase values.")

    if normalized_tab != "ALL":
        db_state = parse_player_state_api_value(normalized_tab)
        if db_state is None:
            raise ParseError(detail="Invalid tab.")
        queryset = queryset.filter(state=db_state)

    players = []
    for profile in queryset.order_by("user__first_name", "user__last_name", "user__email"):
        players.append(
            {
                "id": profile.user.id,
                "name": profile.user.name,
                "position": build_position_payload(profile.position),
                "state": normalize_player_state(profile.state),
                "avatar_url": build_media_value_url(profile.avatar),
                "last_activity": profile.user.last_seen_at,
            }
        )

    return {"players": players}
