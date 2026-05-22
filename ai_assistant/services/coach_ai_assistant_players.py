import re

from accounts.models import PlayerProfile
from accounts.serializers.position import build_position_payload


def find_coach_player_matches(*, coach_user, message):
    normalized_message = _normalize_search_text(message)
    name_hint = _extract_name_hint(message)
    normalized_hint = _normalize_search_text(name_hint)

    profiles = (
        PlayerProfile.objects.filter(coach=coach_user)
        .select_related("user", "position")
        .order_by("user__first_name", "user__last_name", "user__email")
    )

    scored_matches = []
    for profile in profiles:
        player = profile.user
        full_name = _normalize_search_text(player.name)
        first_name = _normalize_search_text(player.first_name)
        last_name = _normalize_search_text(player.last_name)
        email_prefix = _normalize_search_text(player.email.split("@", 1)[0])

        score = _match_score(
            candidates=[full_name, first_name, last_name, email_prefix],
            normalized_message=normalized_message,
            normalized_hint=normalized_hint,
        )
        if score > 0:
            scored_matches.append((score, profile))

    scored_matches.sort(
        key=lambda item: (
            -item[0],
            item[1].user.first_name.lower(),
            item[1].user.last_name.lower(),
            item[1].user.email.lower(),
        )
    )
    return [profile for _, profile in scored_matches]


def resolve_coach_player_targets(*, coach_user, message):
    name_hints = _extract_name_hints(message)
    if not name_hints:
        matches = find_coach_player_matches(coach_user=coach_user, message=message)
        if not matches:
            return {"status": "no_match", "profiles": [], "name_hint": ""}
        if len(matches) > 1:
            return {"status": "ambiguous", "profiles": matches, "name_hint": ""}
        return {"status": "matched", "profiles": matches, "name_hint": ""}

    profiles = list(
        PlayerProfile.objects.filter(coach=coach_user)
        .select_related("user", "position")
        .order_by("user__first_name", "user__last_name", "user__email")
    )

    matched_profiles = []
    for hint in name_hints:
        hint_matches = [
            profile
            for profile in profiles
            if _matches_name_hint(profile, hint)
        ]
        if not hint_matches:
            return {"status": "no_match", "profiles": [], "name_hint": hint}
        if len(hint_matches) > 1:
            return {"status": "ambiguous", "profiles": hint_matches, "name_hint": hint}
        if hint_matches[0] not in matched_profiles:
            matched_profiles.append(hint_matches[0])

    return {"status": "matched", "profiles": matched_profiles, "name_hint": ""}


def build_select_player_actions(profiles):
    actions = []
    for profile in profiles:
        actions.append(
            {
                "type": "select_player",
                "label": f"Use {profile.user.name or profile.user.email}",
                "player_id": str(profile.user_id),
                "player": {
                    "id": str(profile.user_id),
                    "name": profile.user.name,
                    "position": build_position_payload(profile.position),
                    "avatar_url": None,
                },
                "requires_confirmation": False,
            }
        )
    return actions


def build_player_context(profile):
    return {
        "id": str(profile.user_id),
        "name": profile.user.name,
        "position": build_position_payload(profile.position),
        "state": profile.state,
        "fitness_level": profile.fitness_level,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "foot": profile.foot,
    }


def format_player_names(profiles):
    names = [profile.user.name or profile.user.email for profile in profiles]
    if not names:
        return "the selected players"
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _matches_name_hint(profile, hint):
    normalized_hint = _normalize_search_text(hint)
    if not normalized_hint:
        return False

    player = profile.user
    full_name = _normalize_search_text(player.name)
    first_name = _normalize_search_text(player.first_name)
    last_name = _normalize_search_text(player.last_name)
    email_prefix = _normalize_search_text(player.email.split("@", 1)[0])
    candidates = {full_name, first_name, last_name, email_prefix}

    if normalized_hint in candidates:
        return True
    if " " in normalized_hint:
        return bool(full_name and (normalized_hint in full_name or full_name in normalized_hint))
    return normalized_hint in set(full_name.split())


def _match_score(*, candidates, normalized_message, normalized_hint):
    score = 0
    for candidate in candidates:
        if not candidate:
            continue
        if normalized_hint and candidate == normalized_hint:
            score = max(score, 100 + len(candidate))
        elif normalized_hint and (candidate in normalized_hint or normalized_hint in candidate):
            score = max(score, 80 + min(len(candidate), len(normalized_hint)))
        elif _contains_token_phrase(normalized_message, candidate):
            score = max(score, 50 + len(candidate))
    return score


def _contains_token_phrase(haystack, needle):
    if not haystack or not needle:
        return False
    return f" {needle} " in f" {haystack} "


def _extract_name_hint(message):
    text = message or ""
    for match in re.finditer(r"\b(?:for|with|players?|athletes?)\s+", text, flags=re.IGNORECASE):
        hint = _clean_name_hint(text[match.end(): match.end() + 160])
        if hint:
            return hint
    return ""


def _extract_name_hints(message):
    hint = _extract_name_hint(message)
    if not hint:
        return []
    parts = re.split(r"\s*(?:,|&|\band\b|\+)\s*", hint, flags=re.IGNORECASE)
    return [
        _clean_name_hint(part)
        for part in parts
        if _clean_name_hint(part)
    ]


def _clean_name_hint(value):
    hint = str(value or "")
    hint = re.split(
        (
            r"\b(?:both\s+)?(?:to\s+)?(?:start|starts|starting|begin|begins|beginning|"
            r"end|ends|ending|finish|finishes|finishing)\b"
            r"|\b(?:from|until|through|by|on)\s+(?:the\s+)?(?:current\s+day|today|tomorrow(?:\s+day)?)\b"
            r"|\b(?:today|current\s+day|tomorrow(?:\s+day)?|next|this|week|month|please)\b"
        ),
        hint,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    hint = re.sub(r"\b(?:both|together|all)\b.*$", "", hint, flags=re.IGNORECASE)
    hint = re.sub(r"\b(?:plan|plans|program|programs|training|session|sessions)\b", "", hint, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", hint).strip(" .,'-")


def _normalize_search_text(value):
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()
