from rest_framework.exceptions import APIException


class ConflictError(APIException):
    status_code  = 409
    default_detail = "Conflict."
    default_code   = "conflict"
