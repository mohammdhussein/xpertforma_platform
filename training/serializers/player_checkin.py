from rest_framework import serializers

from accounts.exceptions import InvalidInputError
from training.models import PlayerCheckin
from training.statuses import SleepQuality, VALID_SORE_ZONES


VALID_SLEEP_QUALITY_VALUES = [choice.value for choice in SleepQuality]


class SubmitCheckinSerializer(serializers.Serializer):
    sleep_hours   = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=24)
    sleep_quality = serializers.CharField()
    mood          = serializers.IntegerField(min_value=1, max_value=5)
    sore_zones    = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )

    def validate_sleep_quality(self, value):
        if value not in VALID_SLEEP_QUALITY_VALUES:
            raise InvalidInputError(
                "Invalid sleep_quality.",
                expected=VALID_SLEEP_QUALITY_VALUES,
            )
        return value

    def validate_sore_zones(self, value):
        invalid_zones = [zone for zone in value if zone not in VALID_SORE_ZONES]
        if invalid_zones:
            raise InvalidInputError(
                "Invalid sore_zones value.",
                expected=list(VALID_SORE_ZONES),
            )
        return value


class CheckinDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlayerCheckin
        fields = [
            "id",
            "player_id",
            "date",
            "sleep_hours",
            "sleep_quality",
            "mood",
            "sore_zones",
            "readiness_score",
            "created_at",
        ]


class TodayStatusSerializer(serializers.Serializer):
    submitted = serializers.BooleanField()
    checkin   = CheckinDetailSerializer(allow_null=True)
