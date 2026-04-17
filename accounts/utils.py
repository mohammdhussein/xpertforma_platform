from datetime import datetime

from django.utils import timezone


def duration_minutes(start_time, end_time):
    if not start_time or not end_time:
        return 0
    start_dt = datetime.combine(timezone.localdate(), start_time)
    end_dt = datetime.combine(timezone.localdate(), end_time)
    return max(int((end_dt - start_dt).total_seconds() // 60), 0)
