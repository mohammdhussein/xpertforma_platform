from django.conf import settings

import requests


class OllamaServiceUnavailable(Exception):
    pass


class OllamaClient:
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        last_error = None
        for model in _model_candidates():
            try:
                return self._post_chat(model, messages)
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                last_error = exc
        raise OllamaServiceUnavailable("AI service is unavailable") from last_error

    def _post_chat(self, model, messages):
        base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "think": False,
                "messages": messages,
                "stream": False,
                "format": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "cards": {"type": "array"},
                        "actions": {"type": "array"},
                        "suggested_questions": {"type": "array"},
                    },
                    "required": ["answer", "cards", "actions", "suggested_questions"],
                    "additionalProperties": False,
                },
                "options": {
                    "temperature": getattr(settings, "AI_RESPONSE_TEMPERATURE", 0),
                    "num_ctx": 2048,
                    "num_predict": getattr(settings, "OLLAMA_NUM_PREDICT", 220),
                    "seed": getattr(settings, "AI_RANDOM_SEED", 7),
                },
            },
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["message"]["content"]
        if content is None:
            raise ValueError("Ollama response did not include message.content")
        return str(content)


def _model_candidates():
    models = [
        getattr(settings, "OLLAMA_CHAT_MODEL", "qwen3:4b"),
        getattr(settings, "OLLAMA_FALLBACK_MODEL", "llama3.2:3b"),
    ]
    seen = set()
    for model in models:
        if model and model not in seen:
            seen.add(model)
            yield model
