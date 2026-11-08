from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

VERIFICATION_REQUIRED = {
    "detail": (
        "Verify your email address before publishing contributions, commenting, "
        "or reacting."
    ),
    "code": "email_not_verified",
}


class IsEmailVerified(BasePermission):
    """Require a verified email for actions that publish or amplify content."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.email_verified:
            return True
        raise PermissionDenied(detail=VERIFICATION_REQUIRED)
