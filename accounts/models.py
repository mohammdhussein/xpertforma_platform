import uuid
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


def split_full_name(value):
    parts = (value or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        full_name = extra.pop("name", None)
        if full_name is not None and not (extra.get("first_name") or extra.get("last_name")):
            first_name, last_name = split_full_name(full_name)
            extra["first_name"] = first_name
            extra["last_name"] = last_name
        extra.setdefault("first_name", "")
        extra.setdefault("last_name", "")
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    @property
    def name(self):
        return " ".join(part for part in [self.first_name, self.last_name] if part).strip()

    @name.setter
    def name(self, value):
        self.first_name, self.last_name = split_full_name(value)

    def __str__(self):
        return self.email


class Role(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.role_name


class UserRole(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey("accounts.Role", on_delete=models.CASCADE, related_name="role_users")

    class Meta:
        unique_together = ("user", "role")


# accounts/models.py
class CoachProfile(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="coach_profile")
    certificate_image = models.ImageField(upload_to="coach_certificates/", null=True, blank=True)
    phone_number = models.CharField(max_length=32, null=True, blank=True)
    approval_status = models.CharField(max_length=20, default="PENDING")  # pending/approved/rejected
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="approved_coaches")
    rejection_reason = models.TextField(blank=True)


class Position(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, editable=False)
    name = models.CharField(max_length=60, unique=True)
    code = models.CharField(max_length=10, unique=True)
    category = models.CharField(max_length=30)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class PlayerProfile(models.Model):
    FOOT_RIGHT = "RIGHT"
    FOOT_LEFT = "LEFT"
    FOOT_BOTH = "BOTH"
    FOOT_CHOICES = [
        (FOOT_RIGHT, "Right"),
        (FOOT_LEFT, "Left"),
        (FOOT_BOTH, "Both"),
    ]

    STATE_ACTIVE = "ACTIVE"
    STATE_INJURED = "INJURED"
    STATE_NEEDS_REVIEW = "NEEDS_REVIEW"
    STATE_CHOICES = [
        (STATE_ACTIVE, "Active"),
        (STATE_INJURED, "Injured"),
        (STATE_NEEDS_REVIEW, "Needs Review"),
    ]

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True,
                                related_name="player_profile")

    # one coach has many players
    coach = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="coached_players",
        limit_choices_to={"user_roles__role__role_name": "Coach"},
    )

    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    foot = models.CharField(max_length=10, choices=FOOT_CHOICES, null=True, blank=True)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_ACTIVE)
    position = models.ForeignKey("accounts.Position", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="player_profiles")
    fitness_level = models.CharField(max_length=40, blank=True)
    login_status = models.CharField(max_length=20, default="FIRST_LOGIN")
    avatar = models.ImageField(upload_to="player_avatars/", null=True, blank=True)

    # team is in organizations app; use string ref to avoid circular imports
    team = models.ForeignKey("organizations.Team", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="players")


class PlayerPerformanceSnapshot(models.Model):
    METRIC_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]

    player = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="performance_snapshots",
    )
    recorded_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_player_performance_snapshots",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    speed = models.PositiveSmallIntegerField(null=True, blank=True, validators=METRIC_VALIDATORS)
    stamina = models.PositiveSmallIntegerField(null=True, blank=True, validators=METRIC_VALIDATORS)
    strength = models.PositiveSmallIntegerField(null=True, blank=True, validators=METRIC_VALIDATORS)
    skills = models.PositiveSmallIntegerField(null=True, blank=True, validators=METRIC_VALIDATORS)
    note = models.TextField(blank=True)
    focus_area_override = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]
        indexes = [
            models.Index(fields=["player", "recorded_at"]),
        ]


class ManagerProfile(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True,
                                related_name="manager_profile")
    club = models.ForeignKey("organizations.Club", on_delete=models.CASCADE, related_name="managers")


class PasswordSetupToken(models.Model):
    PURPOSE_SET_PASSWORD = "SET_PASSWORD"
    PURPOSE_CHOICES = (
        (PURPOSE_SET_PASSWORD, "Set Password"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_setup_tokens",
    )
    token = models.CharField(max_length=64, unique=True)
    purpose = models.CharField(
        max_length=32,
        choices=PURPOSE_CHOICES,
        default=PURPOSE_SET_PASSWORD,
    )
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.purpose}"
