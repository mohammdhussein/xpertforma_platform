from datetime import date

from training.models import PlayerCheckin


def get_today_checkin(player_user, today: date | None = None) -> PlayerCheckin | None:
    return PlayerCheckin.objects.filter(
        player=player_user, date=today or date.today()
    ).first()


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
