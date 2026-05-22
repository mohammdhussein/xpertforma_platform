from rest_framework import serializers


class StrictFieldsSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError({"detail": "Expected a JSON object."})

        allowed_fields = set(self.fields)
        unknown_fields = sorted(set(data) - allowed_fields)
        if unknown_fields:
            raise serializers.ValidationError(
                {
                    "detail": "Unsupported field(s) in request.",
                    "unsupported_fields": unknown_fields,
                    "allowed_fields": sorted(allowed_fields),
                }
            )

        return super().to_internal_value(data)


class AIChatRequestSerializer(StrictFieldsSerializer):
    message = serializers.CharField(max_length=2000, trim_whitespace=True)
    response_format = serializers.ChoiceField(
        choices=("html",),
        required=False,
        default="html",
    )


class AIActionConfirmRequestSerializer(StrictFieldsSerializer):
    action_type = serializers.ChoiceField(choices=("create_training_plan_from_option",))
    draft_id = serializers.UUIDField()
    selected_option_id = serializers.CharField(max_length=40, trim_whitespace=True)
