from datetime import date

from training.models import PlayerCheckin


def get_today_checkin(
        player_user,
        today: date | None = None,
        *,
        for_update: bool = False,
) -> PlayerCheckin | None:
    qs = PlayerCheckin.objects.filter(player=player_user, date=today or date.today())
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def create_checkin(
        player_user,
        *,
        checkin_date,
        sleep_hours,
        sleep_quality,
        mood,
        sore_zones,
        readiness_score,
) -> PlayerCheckin:
    return PlayerCheckin.objects.create(
        player=player_user,
        date=checkin_date,
        sleep_hours=sleep_hours,
        sleep_quality=sleep_quality,
        mood=mood,
        sore_zones=sore_zones,
        readiness_score=readiness_score,
    )


def update_checkin(
        checkin: PlayerCheckin,
        *,
        sleep_hours,
        sleep_quality,
        mood,
        sore_zones,
        readiness_score,
) -> PlayerCheckin:
    checkin.sleep_hours = sleep_hours
    checkin.sleep_quality = sleep_quality
    checkin.mood = mood
    checkin.sore_zones = sore_zones
    checkin.readiness_score = readiness_score
    checkin.save(update_fields=[
        "sleep_hours",
        "sleep_quality",
        "mood",
        "sore_zones",
        "readiness_score",
        "updated_at",
    ])
    return checkin
