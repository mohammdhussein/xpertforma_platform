from django.db import models
# training/models.py
import uuid
from django.db import models

class TrainingPlan(models.Model):
    plan_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="created_training_plans")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(default=0)
    difficulty = models.CharField(max_length=30, blank=True)

    players = models.ManyToManyField(
        "accounts.User",
        through="TrainingPlanPlayer",
        through_fields=("plan", "player"),
        related_name="assigned_training_plans",
        limit_choices_to={"user_roles__role__role_name": "Player"},
    )

    def __str__(self):
        return self.title


class TrainingSession(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey("training.TrainingPlan", on_delete=models.CASCADE, related_name="sessions")

    title = models.CharField(max_length=120, blank=True)
    session_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["session_date", "start_time"]


class TrainingPlanPlayer(models.Model):
    plan = models.ForeignKey("training.TrainingPlan", on_delete=models.CASCADE)
    player = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    assigned_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="plan_assignments_made")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("plan", "player")
