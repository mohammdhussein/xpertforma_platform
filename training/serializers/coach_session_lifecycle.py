from rest_framework import serializers


class CoachSessionStartSerializer(serializers.Serializer):
    presentPlayerIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        allow_empty=True,
    )
