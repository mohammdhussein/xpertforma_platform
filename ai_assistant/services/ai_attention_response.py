import re


ATTENTION_TOKENS = {"attention", "risk", "alert", "alerts"}


def stabilize_attention_response(response_data, *, context_data, route, user_message):
    if not _is_attention_question(route, user_message):
        return response_data

    selected_player = (context_data.get("players") or {}).get("selected_player")
    if not isinstance(selected_player, dict):
        return response_data

    stable_response = build_selected_player_attention_response(selected_player)
    if stable_response is None:
        return response_data
    return stable_response


def _is_attention_question(route, user_message):
    route_sources = set(route.get("data_sources") or [])
    route_text = " ".join(
        [
            str(user_message or ""),
            str(route.get("question_type") or ""),
            " ".join(route_sources),
        ]
    )
    tokens = set(re.findall(r"[a-z0-9]+", route_text.lower()))
    return bool(tokens & ATTENTION_TOKENS)


def build_selected_player_attention_response(player):
    name = str(player.get("name") or "This player").strip() or "This player"
    needs_attention = bool(player.get("needs_attention"))
    reasons = [
        str(reason).strip().rstrip(".")
        for reason in (player.get("attention_reasons") or [])
        if str(reason).strip()
    ]

    if not needs_attention:
        return {
            "answer": f"No. {name} does not need attention based on the provided data.",
            "cards": [
                {
                    "title": "Attention",
                    "value": "No attention needed",
                    "severity": "INFO",
                }
            ],
            "actions": [],
            "suggested_questions": [
                f"What is {name}'s attendance?",
                f"How is {name}'s progress?",
                f"What is {name}'s latest session?",
            ],
        }

    reason_text = ", ".join(reasons)
    if reason_text:
        reason_label = "this reason" if len(reasons) == 1 else "these reasons"
        answer = f"Yes. {name} needs attention because of {reason_label}: {reason_text}."
    else:
        answer = (
            f"Yes. {name} is marked as needing attention, but the available "
            "context does not include a specific reason."
        )

    cards = [
        {
            "title": "Attention reason",
            "value": reason,
            "severity": _severity_for_reason(reason),
        }
        for reason in reasons[:3]
    ]
    if not cards:
        cards = [
            {
                "title": "Attention",
                "value": "Needs attention",
                "severity": "WARNING",
            }
        ]

    return {
        "answer": answer,
        "cards": cards,
        "actions": [],
        "suggested_questions": [
            f"What is {name}'s attendance?",
            f"How is {name}'s progress?",
            f"What is {name}'s latest session?",
        ],
    }


def _severity_for_reason(reason):
    lowered = reason.lower()
    if "injured" in lowered or "critical" in lowered:
        return "CRITICAL"
    if "missed" in lowered or "low" in lowered:
        return "WARNING"
    return "INFO"
