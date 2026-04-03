from rest_framework import serializers

from accounts.models import Position


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "name", "code", "category"]


class PositionSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True, allow_null=True)


def build_position_payload(position, fallback_name=""):
    return {
        "id": getattr(position, "id", None),
        "name": getattr(position, "name", None) or (fallback_name or ""),
        "code": getattr(position, "code", None),
    }
