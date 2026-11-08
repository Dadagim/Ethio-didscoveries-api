from django.urls import path

from .views import (
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    ResendVerificationView,
    VerifyEmailView,
)

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path(
        "auth/verify-email/",
        VerifyEmailView.as_view(),
        name="auth-verify-email",
    ),
    path(
        "auth/verify-email/resend/",
        ResendVerificationView.as_view(),
        name="auth-verify-email-resend",
    ),
    path("profiles/me/", MeView.as_view(), name="profile-me"),
]
