"""Security headers shared by every Django-rendered response."""

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "frame-src https://www.youtube-nocookie.com; "
    "img-src 'self' data: https://i.ytimg.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'self'"
)


class ContentSecurityPolicyMiddleware:
    """Attach a conservative CSP to responses served by Django.

    The single-page app is served by its own host, so the production web server
    must send the same policy for it. Django only renders the admin and error
    pages, and the admin needs a more permissive policy, so it is excluded.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/admin/"):
            response.headers.setdefault(
                "Content-Security-Policy",
                CONTENT_SECURITY_POLICY,
            )
        return response
