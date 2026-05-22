from rest_framework import serializers

from ai_assistant.coach_ai_assistant_serializers import (
    AIActionConfirmRequestSerializer,
    AIChatRequestSerializer,
)


class AIChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField(allow_blank=True)
    render_type = serializers.ChoiceField(choices=("html",))
    html = serializers.CharField(allow_blank=True)
    cards = serializers.ListField(child=serializers.DictField(), required=False)
    actions = serializers.ListField(child=serializers.DictField(), required=False)
    suggested_questions = serializers.ListField(child=serializers.CharField(), required=False)


__all__ = [
    "AIActionConfirmRequestSerializer",
    "AIChatRequestSerializer",
    "AIChatResponseSerializer",
]
