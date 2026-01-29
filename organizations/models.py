from django.db import models

# organizations/models.py
import uuid
from django.db import models

class Club(models.Model):
    club_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    subscription_status = models.CharField(max_length=50, default="free")

    def __str__(self):
        return self.name


class Team(models.Model):
    team_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey("organizations.Club", on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=120)
    age_group = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return f"{self.name} ({self.age_group})"
