import uuid
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.core.exceptions import ValidationError

from training.statuses import Intensity, InsightTag, SleepQuality


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

    status = models.CharField(max_length=20, default="DRAFT")  # DRAFT / PUBLISHED / ACTIVE

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
    SESSION_TYPE_GROUP = "GROUP"
    SESSION_TYPE_TEAM = "TEAM"
    SESSION_TYPE_INDIVIDUAL = "INDIVIDUAL"
    SESSION_TYPE_CHOICES = [
        (SESSION_TYPE_GROUP, "Group"),
        (SESSION_TYPE_TEAM, "Team"),
        (SESSION_TYPE_INDIVIDUAL, "Individual"),
    ]

    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    plan = models.ForeignKey(
        "training.TrainingPlan",
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    title = models.CharField(max_length=120, blank=True)
    session_date = models.DateField()
    session_type = models.CharField(
        max_length=20,
        choices=SESSION_TYPE_CHOICES,
        default=SESSION_TYPE_GROUP,
    )
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    notes            = models.TextField(blank=True)
    intensity        = models.CharField(
        max_length=10,
        choices=Intensity.choices,
        default=Intensity.MEDIUM,
    )
    location         = models.CharField(max_length=120, blank=True)
    squad_size       = models.PositiveIntegerField(null=True, blank=True)
    coach_note       = models.TextField(blank=True)

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


class PlayerSessionProgress(models.Model):
    STATUS_CHOICES = [
        ("NOT_STARTED", "Not Started"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED",   "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="session_progress")
    session = models.ForeignKey("training.TrainingSession", on_delete=models.CASCADE, related_name="player_progress")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NOT_STARTED")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("player", "session")


class SessionLifecycle(models.Model):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"
    STATUS_CHOICES = [
        (NOT_STARTED, "Not Started"),
        (IN_PROGRESS, "In Progress"),
        (COMPLETED,   "Completed"),
    ]

    session = models.OneToOneField(
        "training.TrainingSession",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="lifecycle",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NOT_STARTED)
    started_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sessions_started",
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sessions_ended",
    )


class SessionAttendance(models.Model):
    PRESENT = "PRESENT"
    LATE    = "LATE"
    STATUS_CHOICES = [
        (PRESENT, "Present"),
        (LATE,    "Late"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        "training.TrainingSession",
        on_delete=models.CASCADE,
        related_name="attendance",
    )
    player = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PRESENT)
    marked_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_marked",
    )
    marked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("session", "player")


class PlayerCheckin(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="checkins",
    )
    date            = models.DateField()
    sleep_hours     = models.DecimalField(max_digits=4, decimal_places=2)
    sleep_quality   = models.CharField(max_length=10, choices=SleepQuality.choices)
    mood            = models.PositiveSmallIntegerField()
    sore_zones      = ArrayField(models.CharField(max_length=20), default=list, blank=True)
    readiness_score = models.PositiveSmallIntegerField()
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("player", "date")
        ordering = ["-date"]


class WeeklyLoad(models.Model):
    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player             = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_loads",
    )
    week_start         = models.DateField()
    distance_km        = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    acute_load         = models.IntegerField(default=0)
    chronic_load       = models.IntegerField(default=0)
    sessions_completed = models.PositiveIntegerField(default=0)
    sessions_planned   = models.PositiveIntegerField(default=0)
    streak_days        = models.PositiveIntegerField(default=0)
    top_sprint_kmh     = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    top_sprint_pb_kmh  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("player", "week_start")


class AIInsight(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_insights",
    )
    date       = models.DateField()
    tag        = models.CharField(max_length=15, choices=InsightTag.choices)
    text       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("player", "date", "tag")
        ordering = ["-date"]
