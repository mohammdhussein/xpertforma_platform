# Project Rules

- If any API endpoint changes in behavior, request body, query params, path params, or response shape, update `api-reference.html` in the same change.
- Only create a dedicated git branch when the user explicitly asks for one.
- Dedicated feature branches must use the `feature/` prefix.
- Any API player object must expose `position` as an object and include `avatar_url`.
- File names across all layers (views, services, serializers, queries, tests) must match the feature they serve using the pattern `{role}_{feature}.py` (e.g. `player_home.py`, `coach_training_plans.py`). Never use generic names like `home.py`, `utils.py`, or `helpers.py`.
