"""Environment rules for secrets, debug mode, and the database URL."""

from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

# These strings have appeared in source or in the example env file.
# They must never boot a non-debug server.
PUBLIC_SECRET_KEYS = {
    "change-me-to-a-long-random-string",
    "django-insecure-development-only-change-this-before-deploying",
}

_TEST_SECRET_KEY = "test-only-secret-key-not-for-production"


def resolve_debug(raw):
    """Debug is off unless the environment explicitly turns it on."""

    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def resolve_secret_key(raw, *, debug, testing):
    """Require a real secret. Tests may use a fixed key when none is configured."""

    key = (raw or "").strip()
    if testing and not key:
        key = _TEST_SECRET_KEY
    if not key:
        raise ImproperlyConfigured(
            "SECRET_KEY is required. Set it in the environment. "
            "The application does not ship a fallback key."
        )
    if key in PUBLIC_SECRET_KEYS and not debug and not testing:
        raise ImproperlyConfigured(
            "SECRET_KEY is a public placeholder. Set a unique secret "
            "before running with DEBUG off."
        )
    return key


def database_from_url(url):
    """Turn DATABASE_URL into a Django DATABASES['default'] dictionary."""

    parsed = urlparse((url or "").strip())
    scheme = (parsed.scheme or "").lower()
    query = parse_qs(parsed.query)

    if scheme in {"postgres", "postgresql"}:
        engine = "django.db.backends.postgresql"
        name = unquote(parsed.path.lstrip("/"))
    elif scheme in {"sqlite", "sqlite3"}:
        engine = "django.db.backends.sqlite3"
        path = unquote(parsed.path or "")
        if path in {"", "/", "/:memory:"} or url.rstrip("/").endswith(":memory:"):
            name = ":memory:"
        else:
            name = path[1:] if path.startswith("/") else path
    else:
        raise ImproperlyConfigured(
            f"Unsupported DATABASE_URL scheme '{scheme or 'missing'}'. "
            "Use postgresql:// or sqlite://."
        )

    if not name:
        raise ImproperlyConfigured("DATABASE_URL is missing a database name.")

    config = {
        "ENGINE": engine,
        "NAME": name,
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": "" if parsed.port is None else str(parsed.port),
    }
    options = {}
    if query.get("sslmode"):
        options["sslmode"] = query["sslmode"][0]
    if options:
        config["OPTIONS"] = options
    return config
