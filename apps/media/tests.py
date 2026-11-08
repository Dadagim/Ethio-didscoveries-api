from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.communities.models import Community, CommunityMembership
from apps.posts.models import Post

from .models import MediaAsset, MediaAttachment
from .services import UnsupportedVideoURLError, parse_youtube_url

User = get_user_model()

VIDEO_ID = "dQw4w9WgXcQ"
CANONICAL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
EMBED = f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}"
THUMBNAIL = f"https://i.ytimg.com/vi/{VIDEO_ID}/hqdefault.jpg"


class YouTubeParsingTests(SimpleTestCase):
    def test_accepts_common_youtube_url_forms(self):
        urls = [
            f"https://www.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtube.com/watch?v={VIDEO_ID}&t=42s",
            f"https://m.youtube.com/watch?v={VIDEO_ID}",
            f"https://music.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}?si=tracking",
            f"https://www.youtube.com/embed/{VIDEO_ID}",
            f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
            f"https://www.youtube.com/shorts/{VIDEO_ID}",
            f"https://www.youtube.com/live/{VIDEO_ID}",
        ]

        for url in urls:
            with self.subTest(url=url):
                info = parse_youtube_url(url)
                self.assertEqual(info["provider"], MediaAsset.Provider.YOUTUBE)
                self.assertEqual(info["external_id"], VIDEO_ID)
                self.assertEqual(info["canonical_url"], CANONICAL)
                self.assertEqual(info["embed_url"], EMBED)
                self.assertEqual(info["thumbnail_url"], THUMBNAIL)

    def test_rejects_unsafe_or_unsupported_values(self):
        values = [
            "",
            "   ",
            "<iframe src='https://www.youtube.com/embed/x'></iframe>",
            "javascript:alert(1)",
            "ftp://youtube.com/watch?v=" + VIDEO_ID,
            "https://vimeo.com/123456",
            "https://youtube.com.evil.example/watch?v=" + VIDEO_ID,
            "https://www.youtube.com/watch",
            "https://youtu.be/",
            "https://youtu.be/too-short",
            "https://www.youtube.com/watch?v=" + ("x" * 12),
        ]

        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(UnsupportedVideoURLError):
                    parse_youtube_url(value)

    def test_rejects_urls_with_credentials(self):
        with self.assertRaises(UnsupportedVideoURLError):
            parse_youtube_url(f"https://user:pass@youtube.com/watch?v={VIDEO_ID}")


class ExternalVideoPostTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="SecurePass!2026",
            email_verified=True,
        )
        self.community = Community.objects.create(
            name="Open Science",
            description="Open discussion.",
            owner=self.owner,
            visibility=Community.Visibility.PUBLIC,
        )
        CommunityMembership.objects.create(
            community=self.community,
            user=self.owner,
            role=CommunityMembership.Role.OWNER,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.owner)

    def payload(self, **overrides):
        data = {
            "community_id": self.community.id,
            "title": "Bench recording",
            "content": "What we observed during the run.",
            "type": Post.Type.RESEARCH,
        }
        data.update(overrides)
        return data

    def test_creating_research_post_with_video_attaches_safe_playback_data(self):
        response = self.client.post(
            "/api/posts/",
            self.payload(video_url=f"https://youtu.be/{VIDEO_ID}"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["media"]), 1)
        media = response.data["media"][0]
        self.assertEqual(media["kind"], MediaAsset.Kind.EXTERNAL_VIDEO)
        self.assertEqual(media["provider"], MediaAsset.Provider.YOUTUBE)
        self.assertEqual(media["embed_url"], EMBED)
        self.assertEqual(media["thumbnail_url"], THUMBNAIL)
        self.assertEqual(media["canonical_url"], CANONICAL)

    def test_project_posts_accept_video(self):
        response = self.client.post(
            "/api/posts/",
            self.payload(type=Post.Type.PROJECT, video_url=CANONICAL),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["media"]), 1)

    def test_discussion_posts_reject_video(self):
        response = self.client.post(
            "/api/posts/",
            self.payload(type=Post.Type.DISCUSSION, video_url=CANONICAL),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("video_url", response.data)
        self.assertEqual(Post.objects.count(), 0)

    def test_invalid_video_url_is_rejected(self):
        response = self.client.post(
            "/api/posts/",
            self.payload(video_url="https://vimeo.com/123456"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("video_url", response.data)
        self.assertEqual(MediaAsset.objects.count(), 0)

    def test_iframe_markup_is_rejected(self):
        response = self.client.post(
            "/api/posts/",
            self.payload(video_url=f"<iframe src='https://youtu.be/{VIDEO_ID}'></iframe>"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("video_url", response.data)

    def test_video_can_be_replaced_on_update(self):
        post = self.client.post(
            "/api/posts/",
            self.payload(video_url=CANONICAL),
            format="json",
        ).data
        other_id = "abcdefghijk"

        response = self.client.patch(
            f"/api/posts/{post['id']}/",
            {"video_url": f"https://youtu.be/{other_id}"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["media"]), 1)
        self.assertEqual(
            response.data["media"][0]["embed_url"],
            f"https://www.youtube-nocookie.com/embed/{other_id}",
        )
        self.assertEqual(MediaAttachment.objects.filter(object_id=post["id"]).count(), 1)

    def test_empty_video_url_removes_the_video(self):
        post = self.client.post(
            "/api/posts/",
            self.payload(video_url=CANONICAL),
            format="json",
        ).data

        response = self.client.patch(
            f"/api/posts/{post['id']}/",
            {"video_url": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["media"], [])
        self.assertEqual(MediaAttachment.objects.filter(object_id=post["id"]).count(), 0)
        # The shared asset survives so other posts keep working.
        self.assertTrue(MediaAsset.objects.filter(external_id=VIDEO_ID).exists())

    def test_changing_type_without_removing_video_is_rejected(self):
        post = self.client.post(
            "/api/posts/",
            self.payload(video_url=CANONICAL),
            format="json",
        ).data

        response = self.client.patch(
            f"/api/posts/{post['id']}/",
            {"type": Post.Type.DISCUSSION},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("type", response.data)

    def test_changing_type_and_removing_video_at_once_is_allowed(self):
        post = self.client.post(
            "/api/posts/",
            self.payload(video_url=CANONICAL),
            format="json",
        ).data

        response = self.client.patch(
            f"/api/posts/{post['id']}/",
            {"type": Post.Type.DISCUSSION, "video_url": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["media"], [])

    def test_asset_is_reused_across_posts(self):
        first = self.client.post(
            "/api/posts/",
            self.payload(title="First", video_url=CANONICAL),
            format="json",
        )
        second = self.client.post(
            "/api/posts/",
            self.payload(title="Second", video_url=f"https://youtu.be/{VIDEO_ID}"),
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MediaAsset.objects.filter(external_id=VIDEO_ID).count(), 1)
        self.assertEqual(MediaAttachment.objects.count(), 2)

    def test_unverified_user_cannot_create_video_post(self):
        unverified = User.objects.create_user(
            username="unverified",
            email="unverified@example.com",
            password="SecurePass!2026",
        )
        CommunityMembership.objects.create(
            community=self.community,
            user=unverified,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        self.client.force_authenticate(user=unverified)

        response = self.client.post(
            "/api/posts/",
            self.payload(video_url=CANONICAL),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_not_verified")
        self.assertEqual(MediaAsset.objects.count(), 0)

    def test_restricted_post_media_is_hidden_from_non_members(self):
        restricted = Community.objects.create(
            name="Restricted Lab",
            description="Members only.",
            owner=self.owner,
            visibility=Community.Visibility.RESTRICTED,
        )
        CommunityMembership.objects.create(
            community=restricted,
            user=self.owner,
            role=CommunityMembership.Role.OWNER,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        post = self.client.post(
            "/api/posts/",
            self.payload(
                community_id=restricted.id,
                video_url=CANONICAL,
            ),
            format="json",
        )
        self.assertEqual(post.status_code, status.HTTP_201_CREATED)

        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="SecurePass!2026",
            email_verified=True,
        )
        self.client.force_authenticate(user=outsider)

        response = self.client.get(f"/api/posts/{post.data['id']}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        feed = self.client.get("/api/posts/")
        self.assertEqual(feed.status_code, status.HTTP_200_OK)
        self.assertNotIn(post.data["id"], [item["id"] for item in feed.data["results"]])
