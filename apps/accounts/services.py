import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .middleware import forget_session, touch_session
from .models import AuthToken

logger = logging.getLogger(__name__)

EMAIL_VERIFY_HOURS = 72
PASSWORD_RESET_HOURS = 2


def hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_token(user, purpose, lifetime):
    AuthToken.objects.filter(
        user=user,
        purpose=purpose,
        used_at__isnull=True,
    ).update(used_at=timezone.now())
    raw_token = secrets.token_urlsafe(32)
    AuthToken.objects.create(
        user=user,
        purpose=purpose,
        token_hash=hash_token(raw_token),
        expires_at=timezone.now() + lifetime,
    )
    return raw_token


def consume_token(raw_token, purpose):
    """Consume a single-use token atomically so it cannot be replayed."""

    if not raw_token:
        return None

    token_hash = hash_token(raw_token.strip())
    with transaction.atomic():
        record = (
            AuthToken.objects.select_for_update()
            .select_related("user")
            .filter(token_hash=token_hash, purpose=purpose)
            .first()
        )
        if (
            record is None
            or record.used_at is not None
            or record.expires_at <= timezone.now()
        ):
            return None
        record.used_at = timezone.now()
        record.save(update_fields=["used_at", "updated_at"])
        return record.user


def verify_email(raw_token):
    """Mark an account's email verified if the token is valid."""

    user = consume_token(raw_token, AuthToken.Purpose.EMAIL_VERIFY)
    if user is None:
        return None
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    return user


def resend_verification_email(user):
    """Send a fresh verification link. Returns False for already-verified users."""

    if user.email_verified:
        return False
    send_verification_email(user)
    return True


def _send(subject, body, recipient):
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send email to %s", recipient)


def send_verification_email(user):
    if user.email_verified:
        return
    raw_token = issue_token(
        user,
        AuthToken.Purpose.EMAIL_VERIFY,
        timedelta(hours=EMAIL_VERIFY_HOURS),
    )
    # Put the token in the fragment so it is not sent to the web server in
    # request logs or referrer headers. The frontend posts it back explicitly.
    link = f"{settings.FRONTEND_ORIGIN}/verify-email#token={raw_token}"
    _send(
        "Verify your ETPM email",
        (
            "Confirm this email address so people know the account belongs to you.\n\n"
            f"Open: {link}\n\n"
            f"token: {raw_token}\n"
        ),
        user.email,
    )


def send_password_reset_email(user):
    raw_token = issue_token(
        user,
        AuthToken.Purpose.PASSWORD_RESET,
        timedelta(hours=PASSWORD_RESET_HOURS),
    )
    link = f"{settings.FRONTEND_ORIGIN}/reset-password?token={raw_token}"
    _send(
        "Reset your ETPM password",
        (
            "A password reset was requested for this account.\n\n"
            f"Open: {link}\n\n"
            f"token: {raw_token}\n\n"
            "If you did not ask for this, you can ignore the message.\n"
        ),
        user.email,
    )


def validate_password_pair(user, password, password_confirm):
    errors = {}
    if password != password_confirm:
        errors["password_confirm"] = "The two passwords do not match."
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        errors["password"] = list(exc.messages)
    if errors:
        raise serializers.ValidationError(errors)


def revoke_other_sessions(user, current_session_key):
    keys = list(
        user.tracked_sessions.exclude(session_key=current_session_key).values_list(
            "session_key",
            flat=True,
        )
    )
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
        user.tracked_sessions.filter(session_key__in=keys).delete()


def revoke_all_sessions(user):
    keys = list(user.tracked_sessions.values_list("session_key", flat=True))
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
    user.tracked_sessions.all().delete()


def change_password(request, user, current_password, new_password, new_password_confirm):
    if not user.check_password(current_password):
        raise serializers.ValidationError(
            {"current_password": "The current password is not correct."}
        )
    validate_password_pair(user, new_password, new_password_confirm)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)
    if not request.session.session_key:
        request.session.save()
    revoke_other_sessions(user, request.session.session_key)
    touch_session(request)


def remember_login(request):
    if not request.session.session_key:
        request.session.save()
    touch_session(request)
