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
    last_seen_at = models.DateTimeField(null=True, blank=True)

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


# accounts/models.py
class CoachProfile(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="coach_profile")
    certificate_image = models.ImageField(upload_to="coach_certificates/", null=True, blank=True)
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
    position_label = models.CharField(max_length=40, blank=True)
    position = models.ForeignKey("accounts.Position", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="player_profiles")
    fitness_level = models.CharField(max_length=40, blank=True)
    login_status = models.CharField(max_length=20, default="first_login")
    avatar = models.ImageField(upload_to="player_avatars/", null=True, blank=True)

    # team is in organizations app; use string ref to avoid circular imports
    team = models.ForeignKey("organizations.Team", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="players")


class ManagerProfile(models.Model):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True,
                                related_name="manager_profile")
    club = models.ForeignKey("organizations.Club", on_delete=models.CASCADE, related_name="managers")
