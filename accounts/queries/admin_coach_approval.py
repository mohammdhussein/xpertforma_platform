from accounts.models import CoachProfile
from accounts.statuses import COACH_APPROVAL_PENDING


def get_pending_coach_profiles_queryset():
    return CoachProfile.objects.filter(
        approval_status__iexact=COACH_APPROVAL_PENDING
    ).select_related("user")
