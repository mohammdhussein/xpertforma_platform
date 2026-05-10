DATA_PROFILE = "profile"
DATA_SESSIONS = "sessions"
DATA_ATTENDANCE = "attendance"
DATA_PERFORMANCE = "performance"
DATA_CHECKINS = "checkins"
DATA_PLANS = "plans"
DATA_DASHBOARD = "dashboard"
DATA_PLAYERS = "players"
DATA_COACHES = "coaches"
DATA_POSITIONS = "positions"
DATA_ORGANIZATIONS = "organizations"
DATA_ADMIN = "admin"
DATA_UNKNOWN = "unknown"


DATA_CATALOG = {
    DATA_PROFILE: {
        "description": "Basic authenticated user, player profile, and coach profile data",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": [
            "name",
            "email",
            "role",
            "position",
            "avatar_url",
            "height_cm",
            "weight_kg",
            "foot",
            "state",
            "expected_return_date",
            "approval_status",
        ],
    },
    DATA_PLAYERS: {
        "description": "Coach roster and safe player summaries",
        "roles": ["COACH", "ADMIN"],
        "safe_fields": [
            "name",
            "position",
            "avatar_url",
            "state",
            "needs_attention",
            "expected_return_date",
            "last_activity",
        ],
    },
    DATA_COACHES: {
        "description": "Safe coach account and approval summaries",
        "roles": ["ADMIN"],
        "safe_fields": [
            "name",
            "email",
            "phone_number",
            "approval_status",
            "is_active",
            "player_count",
            "created_at",
        ],
    },
    DATA_SESSIONS: {
        "description": "Training sessions, schedules, status, and compact session counts",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": [
            "title",
            "session_date",
            "start_time",
            "end_time",
            "intensity",
            "location",
            "status",
            "session_type",
            "completed_count",
            "missed_count",
        ],
    },
    DATA_ATTENDANCE: {
        "description": "Attendance records and aggregated attendance summaries",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": [
            "planned",
            "attended",
            "missed",
            "rate",
            "window_days",
            "sessions_with_missed_players",
            "missed_player_names",
        ],
    },
    DATA_PERFORMANCE: {
        "description": "Performance, score, effort, consistency, recovery, progress, and snapshots",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": [
            "score",
            "effort",
            "recovery",
            "consistency",
            "sessions",
            "speed",
            "stamina",
            "strength",
            "skills",
            "focus_area",
        ],
    },
    DATA_CHECKINS: {
        "description": "Readiness check-ins, sleep, mood, sore zones, and recovery signals",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": [
            "date",
            "readiness_score",
            "sleep_hours",
            "sleep_quality",
            "mood",
            "sore_zones",
        ],
    },
    DATA_PLANS: {
        "description": "Training plans and assigned players",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": [
            "title",
            "start_date",
            "end_date",
            "status",
            "sessions_count",
            "assigned_players_count",
        ],
    },
    DATA_DASHBOARD: {
        "description": "Dashboard stats, alerts, and players needing attention",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": [
            "overview_stats",
            "alerts",
            "alerts_total",
            "upcoming_sessions",
            "needs_attention",
        ],
    },
    DATA_POSITIONS: {
        "description": "Football positions available in the platform",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": ["id", "name", "code", "category"],
    },
    DATA_ORGANIZATIONS: {
        "description": "Safe club and team labels linked to players",
        "roles": ["PLAYER", "COACH", "ADMIN"],
        "safe_fields": ["club_name", "team_name", "age_group"],
    },
    DATA_ADMIN: {
        "description": "Safe staff dashboard summaries",
        "roles": ["ADMIN"],
        "safe_fields": [
            "total_users",
            "pending_requests",
            "approved_coaches",
            "total_coaches",
            "total_players",
        ],
    },
}


SENSITIVE_FIELD_KEYWORDS = {
    "password",
    "token",
    "secret",
    "reset",
    "refresh",
    "access",
    "jwt",
    "key",
    "verification",
}


def get_catalog_keywords():
    keywords = set(DATA_CATALOG.keys())
    for item in DATA_CATALOG.values():
        keywords.update(_tokenize(item["description"]))
        for field in item.get("safe_fields", []):
            keywords.update(_tokenize(field))
    keywords.update(
        {
            "xpertforma",
            "backend",
            "app",
            "data",
            "football",
            "team",
            "teams",
            "player",
            "players",
            "coach",
            "coaches",
            "training",
            "session",
            "sessions",
            "readiness",
            "recovery",
            "attendance",
            "progress",
            "performance",
            "profile",
            "dashboard",
            "alert",
            "alerts",
            "invitation",
            "invitations",
            "invite",
            "position",
            "positions",
            "upcoming",
            "latest",
            "scheduled",
            "schedule",
            "date",
            "today",
            "tomorrow",
        }
    )
    return keywords - SENSITIVE_FIELD_KEYWORDS


def _tokenize(value):
    return str(value or "").replace("_", " ").replace("-", " ").lower().split()
