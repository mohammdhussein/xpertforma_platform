from django.utils.dateparse import parse_date
from rest_framework import serializers

from accounts.exceptions import InvalidInputError
from accounts.models import PlayerProfile
from accounts.statuses import (
    VALID_PLAYER_STATE_VALUES,
    normalize_player_state,
    parse_player_state_api_value,
)


DATE_FORMAT = "YYYY-MM-DD"


class CoachPlayerStateUpdateSerializer(serializers.Serializer):
    state = serializers.CharField()
    expected_return_date = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate_state(self, value):
        expected_values = sorted(VALID_PLAYER_STATE_VALUES)
        if value != normalize_player_state(value):
            raise InvalidInputError(
                "Invalid state. Use uppercase values.",
                expected=expected_values,
            )

        parsed = parse_player_state_api_value(value)
        if parsed is None:
            raise InvalidInputError(
                "Invalid state.",
                expected=expected_values,
            )
        return parsed

    def validate_expected_return_date(self, value):
        if value in (None, ""):
            return None

        parsed = parse_date(value)
        if parsed is None:
            raise InvalidInputError(
                "Invalid expected_return_date format.",
                expected=[DATE_FORMAT],
            )
        return parsed

    def validate(self, attrs):
        unknown_fields = sorted(set(self.initial_data.keys()) - set(self.fields.keys()))
        if unknown_fields:
            raise serializers.ValidationError(
                {field_name: ["This field is not allowed."] for field_name in unknown_fields}
            )

        if attrs["state"] != PlayerProfile.STATE_INJURED and "expected_return_date" in self.initial_data:
            raise InvalidInputError("expected_return_date is only allowed when state is INJURED.")

        return attrs

    def update(self, instance, validated_data):
        instance.state = validated_data["state"]
        instance.expected_return_date = (
            validated_data.get("expected_return_date")
            if instance.state == PlayerProfile.STATE_INJURED
            else None
        )
        instance.save(update_fields=["state", "expected_return_date"])
        return instance


class CoachPlayerStateResponseSerializer(serializers.Serializer):
    player_id = serializers.UUIDField()
    state = serializers.CharField()
    expected_return_date = serializers.DateField(allow_null=True)
    needs_attention = serializers.BooleanField()
