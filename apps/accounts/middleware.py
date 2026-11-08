from datetime import timedelta

from django.utils import timezone

from .models import UserSession


class TrackedSessionMiddleware:
    """Remember authenticated browser sessions so people can review them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        session_key = getattr(request.session, "session_key", None)
        if user is not None and user.is_authenticated and session_key:
            touch_session(request)
        return response


def touch_session(request):
    session_key = request.session.session_key
    if not session_key:
        return None

    now = timezone.now()
    existing = UserSession.objects.filter(session_key=session_key).first()
    if (
        existing
        and existing.user_id == request.user.id
        and existing.last_seen
        and existing.last_seen > now - timedelta(minutes=5)
    ):
        return existing

    user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:300]
    ip_address = request.META.get("REMOTE_ADDR") or None
    record, _created = UserSession.objects.update_or_create(
        session_key=session_key,
        defaults={
            "user": request.user,
            "user_agent": user_agent,
            "ip_address": ip_address,
            "last_seen": now,
        },
    )
    return record


def forget_session(request):
    session_key = getattr(request.session, "session_key", None)
    if session_key:
        UserSession.objects.filter(session_key=session_key).delete()
