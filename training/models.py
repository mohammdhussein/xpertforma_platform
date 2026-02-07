import uuid
from django.db import models
from django.core.exceptions import ValidationError

class TrainingPlan(models.Model):
    plan_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    creator = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="created_training_plans"
    )

    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(max_length=20, default="draft")  # draft / published

    players = models.ManyToManyField(
        "accounts.User",
        through="TrainingPlanPlayer",
        through_fields=("plan", "player"),
        related_name="assigned_training_plans",
    )

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("end_date must be after or equal to start_date.")

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return self.title


class TrainingSession(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    plan = models.ForeignKey(
        "training.TrainingPlan",
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    title = models.CharField(max_length=120, blank=True)
    session_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["session_date", "start_time"]


class TrainingPlanPlayer(models.Model):
    plan = models.ForeignKey("training.TrainingPlan", on_delete=models.CASCADE)
    player = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="training_assignments")

    assigned_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="plan_assignments_made"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("plan", "player")
