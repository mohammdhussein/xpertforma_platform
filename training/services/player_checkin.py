from datetime import date

from django.db import transaction

from accounts.exceptions import ConflictError, NotFoundError
from training.queries.player_checkin import (
    create_checkin,
    get_today_checkin,
    update_checkin,
)
from training.statuses import SLEEP_QUALITY_SCORE


def compute_readiness_score(sleep_hours, sleep_quality, mood, sore_zones) -> int:
    hours_component   = min(float(sleep_hours) / 8, 1.0) * 40
    quality_component = SLEEP_QUALITY_SCORE[sleep_quality] * 20
    sleep_score       = hours_component + quality_component   # max 60
    mood_score        = ((mood - 1) / 4) * 25                # max 25
    soreness_penalty  = min(len(sore_zones) * 5, 15)         # max 15 penalty
    raw = sleep_score + mood_score + 15 - soreness_penalty
    return max(0, min(100, round(raw)))


def submit_checkin(player_user, *, sleep_hours, sleep_quality, mood, sore_zones):
    if get_today_checkin(player_user) is not None:
        raise ConflictError("Check-in already submitted for today.")
    score = compute_readiness_score(sleep_hours, sleep_quality, mood, sore_zones)
    return create_checkin(
        player_user,
        checkin_date=date.today(),
        sleep_hours=sleep_hours,
        sleep_quality=sleep_quality,
        mood=mood,
        sore_zones=sore_zones,
        readiness_score=score,
    )


@transaction.atomic
def update_today_checkin(player_user, *, sleep_hours, sleep_quality, mood, sore_zones):
    checkin = get_today_checkin(player_user, for_update=True)
    if checkin is None:
        raise NotFoundError("No check-in submitted for today.")
    score = compute_readiness_score(sleep_hours, sleep_quality, mood, sore_zones)
    return update_checkin(
        checkin,
        sleep_hours=sleep_hours,
        sleep_quality=sleep_quality,
        mood=mood,
        sore_zones=sore_zones,
        readiness_score=score,
    )


def get_today_status(player_user) -> dict:
    checkin = get_today_checkin(player_user)
    return {"submitted": checkin is not None, "checkin": checkin}
