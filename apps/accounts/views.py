from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Profile
from .serializers import (
    ProfileSerializer,
    RegisterSerializer,
    VerifyEmailSerializer,
)
from .services import resend_verification_email, send_verification_email, verify_email

User = get_user_model()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Set the CSRF cookie before the browser submits a write request."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        # Send the verification link only after the account is safely stored.
        # Email failures are logged, never surfaced as a registration failure,
        # because the user can request a new link from the app.
        transaction.on_commit(lambda: send_verification_email(user))
        profile, _ = Profile.objects.get_or_create(user=user)
        return Response(
            {
                "user": ProfileSerializer(
                    profile,
                    context={"request": request},
                ).data
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        identifier = (
            request.data.get("identifier")
            or request.data.get("username")
            or request.data.get("email")
            or ""
        ).strip()
        password = request.data.get("password") or ""

        if not identifier or not password:
            return Response(
                {"detail": "Username/email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = identifier
        if "@" in identifier:
            matched_user = User.objects.filter(email__iexact=identifier).first()
            if matched_user:
                username = matched_user.username

        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid username/email or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        profile, _ = Profile.objects.get_or_create(user=user)
        return Response(
            {
                "user": ProfileSerializer(
                    profile,
                    context={"request": request},
                ).data
            }
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        return Response(
            ProfileSerializer(profile, context={"request": request}).data
        )

    def patch(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class VerifyEmailView(APIView):
    """Consume an emailed verification token and mark the account verified."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verify"

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_email(serializer.validated_data["token"])
        if user is None:
            # The same message covers unknown, expired, and already-used tokens
            # so an attacker cannot probe which tokens exist.
            return Response(
                {
                    "detail": "This verification link is invalid or has expired.",
                    "code": "invalid_verification_token",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "detail": "Your email address is verified.",
                "email_verified": True,
            }
        )


class ResendVerificationView(APIView):
    """Send a fresh verification link to the signed-in account."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verify"

    def post(self, request):
        sent = resend_verification_email(request.user)
        if not sent:
            return Response(
                {
                    "detail": "This email address is already verified.",
                    "email_verified": True,
                }
            )
        return Response(
            {
                "detail": "We sent a new verification link to your email address.",
                "email_verified": False,
            },
            status=status.HTTP_202_ACCEPTED,
        )
