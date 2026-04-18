from rest_framework.exceptions import APIException


def _build_detail(detail, default_detail, expected):
    message = detail if detail is not None else default_detail
    if expected is None:
        return message
    return {"detail": str(message), "expected": list(expected)}


class ConflictError(APIException):
    status_code    = 409
    default_detail = "Conflict."
    default_code   = "conflict"

    def __init__(self, detail=None, code=None, *, expected=None):
        super().__init__(detail=_build_detail(detail, self.default_detail, expected), code=code)


class NotFoundError(APIException):
    status_code    = 404
    default_detail = "Resource not found."
    default_code   = "not_found"

    def __init__(self, detail=None, code=None, *, expected=None):
        super().__init__(detail=_build_detail(detail, self.default_detail, expected), code=code)


class InvalidInputError(APIException):
    status_code    = 400
    default_detail = "Invalid input."
    default_code   = "invalid_input"

    def __init__(self, detail=None, code=None, *, expected=None):
        super().__init__(detail=_build_detail(detail, self.default_detail, expected), code=code)
