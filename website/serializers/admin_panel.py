from rest_framework import serializers


class CoachRequestSummarySerializer(serializers.Serializer):
    pending_requests = serializers.IntegerField()
    approved_coaches = serializers.IntegerField()


class CoachRequestPanelItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField()
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    certificate_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class CoachRequestPanelResponseSerializer(serializers.Serializer):
    summary = CoachRequestSummarySerializer()
    requests = CoachRequestPanelItemSerializer(many=True)
    last_updated = serializers.DateTimeField()


class AdminDashboardSummarySerializer(serializers.Serializer):
    pending_requests = serializers.IntegerField()
    approved_coaches = serializers.IntegerField()
    total_coaches = serializers.IntegerField()
    total_players = serializers.IntegerField()


class AdminDashboardRecentRequestSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class AdminDashboardResponseSerializer(serializers.Serializer):
    summary = AdminDashboardSummarySerializer()
    recent_requests = AdminDashboardRecentRequestSerializer(many=True)


class AdminCoachesSummarySerializer(serializers.Serializer):
    total_coaches = serializers.IntegerField()
    approved_coaches = serializers.IntegerField()
    active_coaches = serializers.IntegerField()


class AdminCoachDirectoryItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField()
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField()
    is_active = serializers.BooleanField()
    joined_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
    player_count = serializers.IntegerField()
    certificate_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AdminCoachDirectoryResponseSerializer(serializers.Serializer):
    summary = AdminCoachesSummarySerializer()
    coaches = AdminCoachDirectoryItemSerializer(many=True)


class AdminCoachToggleActionSerializer(serializers.Serializer):
    coach_id = serializers.UUIDField()
    is_active = serializers.BooleanField()
    status = serializers.CharField()


class AdminPlayersSummarySerializer(serializers.Serializer):
    total_players = serializers.IntegerField()
    assigned_players = serializers.IntegerField()
    needs_setup_players = serializers.IntegerField()


class AdminPlayerDirectoryItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField()
    assigned_coach = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField()
    joined_at = serializers.DateTimeField()
    has_coach = serializers.BooleanField()


class AdminPlayerDirectoryResponseSerializer(serializers.Serializer):
    summary = AdminPlayersSummarySerializer()
    players = AdminPlayerDirectoryItemSerializer(many=True)
