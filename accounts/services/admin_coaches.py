from django.utils import timezone

from accounts.statuses import COACH_APPROVAL_APPROVED, COACH_APPROVAL_REJECTED


def approve_coach_profile(coach_profile, approved_by):
    coach_profile.approval_status = COACH_APPROVAL_APPROVED
    coach_profile.approved_at = timezone.now()
    coach_profile.approved_by = approved_by
    coach_profile.rejection_reason = ""
    coach_profile.save(update_fields=["approval_status", "approved_at", "approved_by", "rejection_reason"])

    return {"coach_id": coach_profile.user_id, "status": COACH_APPROVAL_APPROVED}


def reject_coach_profile(coach_profile, *, reason=""):
    coach_profile.approval_status = COACH_APPROVAL_REJECTED
    coach_profile.approved_at = None
    coach_profile.approved_by = None
    coach_profile.rejection_reason = reason
    coach_profile.save(update_fields=["approval_status", "approved_at", "approved_by", "rejection_reason"])

    return {"coach_id": coach_profile.user_id, "status": "rejected", "reason": reason}
