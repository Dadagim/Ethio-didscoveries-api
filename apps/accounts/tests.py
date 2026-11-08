from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from .models import AuthToken, Profile, Tag
from .services import issue_token

User = get_user_model()


class AuthenticationTests(APITestCase):
    def setUp(self):
        self.payload = {
            "username": "amina",
            "email": "amina@example.com",
            "first_name": "Amina",
            "last_name": "Tesfaye",
            "password": "SecurePass!2026",
            "password_confirm": "SecurePass!2026",
        }

    def test_register_creates_user_profile_and_session(self):
        response = self.client.post("/api/auth/register/", self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["username"], "amina")
        self.assertTrue(User.objects.filter(username="amina").exists())
        self.assertTrue(Profile.objects.filter(user__username="amina").exists())

    def test_register_rejects_duplicate_email(self):
        self.client.post("/api/auth/register/", self.payload, format="json")
        self.client.post("/api/auth/logout/")

        payload = {
            **self.payload,
            "username": "another-user",
            "email": "AMINA@example.com",
        }
        response = self.client.post("/api/auth/register/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_with_email_and_logout(self):
        User.objects.create_user(
            username="dawit",
            email="dawit@example.com",
            password="SecurePass!2026",
        )

        login_response = self.client.post(
            "/api/auth/login/",
            {"identifier": "dawit@example.com", "password": "SecurePass!2026"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.data["user"]["username"], "dawit")

        me_response = self.client.get("/api/profiles/me/")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)

        logout_response = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

        me_after_logout = self.client.get("/api/profiles/me/")
        self.assertIn(
            me_after_logout.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_me_requires_authentication(self):
        response = self.client.get("/api/profiles/me/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_profile_can_be_updated_with_tags(self):
        user = User.objects.create_user(
            username="sara",
            email="sara@example.com",
            password="SecurePass!2026",
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            "/api/profiles/me/",
            {
                "bio": "Engineering student interested in low-cost sensors.",
                "institution": "Addis Ababa University",
                "interests": ["Agriculture", "Electronics"],
                "skills": ["Python", "Circuit design"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["bio"], "Engineering student interested in low-cost sensors.")
        self.assertCountEqual(
            response.data["interest_names"],
            ["Agriculture", "Electronics"],
        )
        self.assertEqual(Tag.objects.count(), 4)

    def test_csrf_endpoint_returns_token_and_sets_cookie(self):
        response = self.client.get("/api/auth/csrf/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["csrfToken"])
        self.assertIn("csrftoken", response.cookies)


class EmailVerificationTests(APITestCase):
    def setUp(self):
        self.payload = {
            "username": "veronika",
            "email": "veronika@example.com",
            "first_name": "Veronika",
            "last_name": "Bekele",
            "password": "SecurePass!2026",
            "password_confirm": "SecurePass!2026",
        }

    def make_user(self, **overrides):
        data = {
            "username": "unverified",
            "email": "unverified@example.com",
            "password": "SecurePass!2026",
        }
        data.update(overrides)
        return User.objects.create_user(**data)

    def test_registration_creates_unverified_user_and_sends_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/auth/register/", self.payload, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["user"]["email_verified"])
        user = User.objects.get(username="veronika")
        self.assertFalse(user.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verify your ETPM email", mail.outbox[0].subject)
        self.assertIn("#token=", mail.outbox[0].body)
        self.assertTrue(
            AuthToken.objects.filter(
                user=user,
                purpose=AuthToken.Purpose.EMAIL_VERIFY,
                used_at__isnull=True,
            ).exists()
        )

    def test_valid_token_verifies_account_and_cannot_be_reused(self):
        user = self.make_user()
        raw_token = issue_token(
            user,
            AuthToken.Purpose.EMAIL_VERIFY,
            timedelta(hours=1),
        )

        first = self.client.post(
            "/api/auth/verify-email/", {"token": raw_token}, format="json"
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertTrue(first.data["email_verified"])
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

        second = self.client.post(
            "/api/auth/verify-email/", {"token": raw_token}, format="json"
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second.data["code"], "invalid_verification_token")

    def test_expired_token_is_rejected(self):
        user = self.make_user()
        raw_token = issue_token(
            user,
            AuthToken.Purpose.EMAIL_VERIFY,
            timedelta(hours=-1),
        )

        response = self.client.post(
            "/api/auth/verify-email/", {"token": raw_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_resend_requires_authentication(self):
        response = self.client.post("/api/auth/verify-email/resend/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_resend_sends_new_link_for_unverified_account(self):
        user = self.make_user()
        self.client.force_authenticate(user=user)

        response = self.client.post("/api/auth/verify-email/resend/")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verify your ETPM email", mail.outbox[0].subject)
        self.assertTrue(
            AuthToken.objects.filter(
                user=user,
                purpose=AuthToken.Purpose.EMAIL_VERIFY,
                used_at__isnull=True,
            ).exists()
        )

    def test_resend_is_a_no_op_for_verified_account(self):
        user = self.make_user(email_verified=True)
        self.client.force_authenticate(user=user)

        response = self.client.post("/api/auth/verify-email/resend/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["email_verified"])
        self.assertEqual(len(mail.outbox), 0)

    def test_profile_reports_verification_state(self):
        user = self.make_user()
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/profiles/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["email_verified"])


def throttled_settings(**rates):
    """Temporarily lower a throttle rate.

    DRF copies ``DEFAULT_THROTTLE_RATES`` onto the throttle class when it is
    imported, so changing Django settings later has no effect. Patch the class
    dictionary instead.
    """

    return patch.dict(ScopedRateThrottle.THROTTLE_RATES, rates, clear=False)


class AuthenticationThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()

    @throttled_settings(login="2/minute")
    def test_login_is_throttled(self):
        for _ in range(2):
            response = self.client.post(
                "/api/auth/login/",
                {"identifier": "nobody", "password": "wrong-password"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        throttled = self.client.post(
            "/api/auth/login/",
            {"identifier": "nobody", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @throttled_settings(register="2/hour")
    def test_registration_is_throttled(self):
        for index in range(2):
            response = self.client.post(
                "/api/auth/register/",
                {
                    "username": f"person{index}",
                    "email": f"person{index}@example.com",
                    "password": "SecurePass!2026",
                    "password_confirm": "SecurePass!2026",
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.client.post("/api/auth/logout/")

        throttled = self.client.post(
            "/api/auth/register/",
            {
                "username": "person3",
                "email": "person3@example.com",
                "password": "SecurePass!2026",
                "password_confirm": "SecurePass!2026",
            },
            format="json",
        )
        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
