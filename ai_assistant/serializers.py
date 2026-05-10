from django.conf import settings
from rest_framework import serializers


class AIChatHistoryMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("user", "assistant"))
    content = serializers.CharField(max_length=2000, trim_whitespace=True)


class AIChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, trim_whitespace=True)
    screen = serializers.CharField(
        required=False,
        allow_blank=True,
        default="UNKNOWN",
        max_length=120,
    )
    selected_player_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    history = AIChatHistoryMessageSerializer(many=True, required=False, default=list, write_only=True)

    def validate_screen(self, value):
        value = (value or "").strip()
        return value or "UNKNOWN"

    def validate_history(self, value):
        max_messages = max(int(getattr(settings, "AI_MAX_HISTORY_MESSAGES", 8)), 0)
        return value[-max_messages:]


class AIChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField(allow_blank=True)
    cards = serializers.ListField(child=serializers.DictField(), required=False)
    actions = serializers.ListField(child=serializers.DictField(), required=False)
    suggested_questions = serializers.ListField(child=serializers.CharField(), required=False)
