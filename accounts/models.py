from django.db import models

# accounts/models.py
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
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
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

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


class CoachProfile(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True, related_name="coach_profile")
    certification_level = models.CharField(max_length=80, blank=True)
    years_experience = models.PositiveIntegerField(default=0)


class PlayerProfile(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True, related_name="player_profile")

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
    position = models.CharField(max_length=40, blank=True)
    fitness_level = models.CharField(max_length=40, blank=True)
    dietary_prefs = models.CharField(max_length=200, blank=True)
    privacy_consents = models.JSONField(default=dict, blank=True)

    # team is in organizations app; use string ref to avoid circular imports
    team = models.ForeignKey("organizations.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="players")


class ManagerProfile(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True, related_name="manager_profile")
    club = models.ForeignKey("organizations.Club", on_delete=models.CASCADE, related_name="managers")
