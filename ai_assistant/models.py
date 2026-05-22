import uuid

from django.conf import settings
from django.db import models


class AIPlanDraft(models.Model):
    draft_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_plan_drafts",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_plan_drafts_as_player",
    )
    target_players = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="ai_plan_drafts_as_target",
        blank=True,
    )
    options = models.JSONField(default=list)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["coach", "expires_at"]),
            models.Index(fields=["player", "expires_at"]),
        ]
        ordering = ["-created_at"]
