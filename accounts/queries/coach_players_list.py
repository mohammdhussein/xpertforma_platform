from django.utils import timezone
from django.db.models import Q

from accounts.exceptions import InvalidInputError
from accounts.files import build_media_value_url
from accounts.models import PlayerProfile
from accounts.services.coach_player_attention import build_coach_player_attention_summary
from accounts.serializers.position import build_position_payload
from accounts.statuses import (
    VALID_PLAYER_STATE_VALUES,
    normalize_player_state,
    parse_player_state_api_value,
)
from xpertforma_platform.api_values import normalize_api_value


NEEDS_ATTENTION_TAB = "NEEDS_ATTENTION"
VALID_COACH_PLAYERS_TAB_VALUES = ["ALL", *sorted(VALID_PLAYER_STATE_VALUES), NEEDS_ATTENTION_TAB]


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
        raise InvalidInputError(
            "Invalid tab. Use uppercase values.",
            expected=VALID_COACH_PLAYERS_TAB_VALUES,
        )

    if normalized_tab == NEEDS_ATTENTION_TAB:
        pass
    elif normalized_tab != "ALL":
        db_state = parse_player_state_api_value(normalized_tab)
        if db_state is None:
            raise InvalidInputError(
                "Invalid tab.",
                expected=VALID_COACH_PLAYERS_TAB_VALUES,
            )
        queryset = queryset.filter(state=db_state)

    players = []
    current_now = timezone.now()
    for profile in queryset.order_by("user__first_name", "user__last_name", "user__email"):
        attention_summary = build_coach_player_attention_summary(profile, now=current_now)
        if normalized_tab == NEEDS_ATTENTION_TAB and not attention_summary["needs_attention"]:
            continue
        players.append(
            {
                "id": profile.user.id,
                "name": profile.user.name,
                "position": build_position_payload(profile.position),
                "state": normalize_player_state(profile.state),
                "needs_attention": attention_summary["needs_attention"],
                "expected_return_date": profile.expected_return_date,
                "avatar_url": build_media_value_url(profile.avatar),
                "last_activity": profile.user.last_seen_at,
            }
        )

    return {"players": players}
