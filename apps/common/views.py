from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Small readiness endpoint used by the frontend and deployment checks."""

    return Response(
        {
            "status": "ok",
            "service": "etpm-api",
            "message": "ETPM backend is running.",
        },
        status=status.HTTP_200_OK,
    )
