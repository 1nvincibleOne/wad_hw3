from django.db import IntegrityError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler, set_rollback


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state."
    default_code = "conflict"


def exception_handler(exc, context):
    """DRF's handler, plus 409 for database rules that block a change."""
    if isinstance(exc, (ProtectedError, IntegrityError)):
        set_rollback()  # undo the request's transaction (ATOMIC_REQUESTS)
    if isinstance(exc, ProtectedError):
        return Response(
            {"detail": "This record is referenced by matches and can't be deleted."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, IntegrityError):
        return Response({"detail": "The change violates a database constraint."}, status=status.HTTP_409_CONFLICT)
    return drf_exception_handler(exc, context)
