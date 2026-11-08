from rest_framework import status
from rest_framework.test import APITestCase


class HealthEndpointTests(APITestCase):
    def test_health_endpoint_is_public(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["service"], "etpm-api")


class ContentSecurityPolicyTests(APITestCase):
    def test_api_responses_allow_only_the_nocookie_video_frame(self):
        response = self.client.get("/api/health/")

        policy = response.headers.get("Content-Security-Policy", "")
        self.assertIn("frame-src https://www.youtube-nocookie.com", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertNotIn("https://www.youtube.com", policy)

    def test_admin_is_excluded(self):
        response = self.client.get("/admin/")

        self.assertNotIn("Content-Security-Policy", response.headers)
