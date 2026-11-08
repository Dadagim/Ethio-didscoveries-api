from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .runtime import resolve_secret_key


class SecretKeyConfigurationTests(SimpleTestCase):
    def test_missing_secret_key_fails_with_actionable_error(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY is required"):
            resolve_secret_key(None, debug=False, testing=False)

    def test_development_placeholder_is_allowed_only_in_debug_mode(self):
        placeholder = "change-me-to-a-long-random-string"

        self.assertEqual(
            resolve_secret_key(placeholder, debug=True, testing=False),
            placeholder,
        )
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "SECRET_KEY is a public placeholder",
        ):
            resolve_secret_key(placeholder, debug=False, testing=False)

    def test_custom_secret_key_is_accepted(self):
        key = "a-locally-generated-secret-key-with-enough-entropy"

        self.assertEqual(
            resolve_secret_key(key, debug=False, testing=False),
            key,
        )
