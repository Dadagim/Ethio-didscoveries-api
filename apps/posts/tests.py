from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.communities.models import Community, CommunityMembership

from .models import Post

User = get_user_model()


class PostTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="SecurePass!2026",
            email_verified=True,
        )
        self.member = User.objects.create_user(
            username="member", email="member@example.com", password="SecurePass!2026",
            email_verified=True,
        )
        self.outsider = User.objects.create_user(
            username="outsider", email="outsider@example.com", password="SecurePass!2026",
            email_verified=True,
        )

        self.public = Community.objects.create(
            name="Public Research",
            description="Open research.",
            owner=self.owner,
            visibility=Community.Visibility.PUBLIC,
        )
        self.private = Community.objects.create(
            name="Private Research",
            description="Closed research.",
            owner=self.owner,
            visibility=Community.Visibility.PRIVATE,
        )
        for community in (self.public, self.private):
            CommunityMembership.objects.create(
                community=community,
                user=self.owner,
                role=CommunityMembership.Role.OWNER,
                status=CommunityMembership.Status.ACTIVE,
                joined_at=timezone.now(),
            )
        CommunityMembership.objects.create(
            community=self.public,
            user=self.member,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )

    def make_post(self, community=None, author=None, **overrides):
        data = {
            "community": community or self.public,
            "author": author or self.member,
            "title": "How can we store solar energy cheaply?",
            "content": "Exploring low-cost battery chemistry for rural micro-grids.",
            "type": Post.Type.QUESTION,
        }
        data.update(overrides)
        return Post.objects.create(**data)

    def post_payload(self, community=None, **overrides):
        payload = {
            "community_id": (community or self.public).id,
            "title": "A low-cost soil moisture sensor",
            "content": "An idea for combining cheap capacitive sensors with an ESP32.",
            "type": Post.Type.IDEA,
            "tags": ["agriculture", "electronics"],
        }
        payload.update(overrides)
        return payload


class PostCreationTests(PostTestCase):
    def test_active_member_can_publish(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post("/api/posts/", self.post_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author"]["username"], "member")
        self.assertEqual(response.data["community"]["slug"], self.public.slug)
        self.assertCountEqual(
            [tag["name"] for tag in response.data["tags"]],
            ["agriculture", "electronics"],
        )

    def test_non_member_cannot_publish(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post("/api/posts/", self.post_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("community_id", response.data)

    def test_anonymous_cannot_publish(self):
        response = self.client.post("/api/posts/", self.post_payload(), format="json")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_unverified_member_cannot_publish(self):
        unverified = User.objects.create_user(
            username="unverified",
            email="unverified@example.com",
            password="SecurePass!2026",
        )
        CommunityMembership.objects.create(
            community=self.public,
            user=unverified,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        self.client.force_authenticate(user=unverified)

        response = self.client.post("/api/posts/", self.post_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_not_verified")


class RestrictedCommunityContentTests(PostTestCase):
    def setUp(self):
        super().setUp()
        self.restricted = Community.objects.create(
            name="Restricted Lab",
            description="Members only.",
            owner=self.owner,
            visibility=Community.Visibility.RESTRICTED,
        )
        CommunityMembership.objects.create(
            community=self.restricted,
            user=self.owner,
            role=CommunityMembership.Role.OWNER,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        self.restricted_post = self.make_post(
            community=self.restricted,
            author=self.owner,
        )

    def test_non_member_cannot_read_restricted_post(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(f"/api/posts/{self.restricted_post.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_read_restricted_post(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(f"/api/posts/{self.restricted_post.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.restricted_post.id)

    def test_restricted_post_is_absent_from_anonymous_feed(self):
        response = self.client.get("/api/posts/")

        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.restricted_post.id, ids)


class PostFeedTests(PostTestCase):
    def test_public_feed_is_visible_anonymously(self):
        public_post = self.make_post()
        self.make_post(community=self.private, author=self.owner)

        response = self.client.get("/api/posts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertIn(public_post.id, ids)
        self.assertEqual(len(ids), 1)

    def test_feed_filters_by_type_and_community(self):
        question = self.make_post(type=Post.Type.QUESTION)
        idea = self.make_post(type=Post.Type.IDEA, title="A different idea")

        by_type = self.client.get("/api/posts/?type=idea")
        by_community = self.client.get(f"/api/posts/?community={self.public.slug}")

        self.assertEqual([item["id"] for item in by_type.data["results"]], [idea.id])
        self.assertEqual(
            {item["id"] for item in by_community.data["results"]},
            {question.id, idea.id},
        )

    def test_private_post_is_hidden_from_outsiders(self):
        private_post = self.make_post(community=self.private, author=self.owner)

        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f"/api/posts/{private_post.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_author_can_edit_and_delete_post(self):
        post = self.make_post()
        self.client.force_authenticate(user=self.member)

        update = self.client.patch(
            f"/api/posts/{post.id}/",
            {"title": "Updated title", "content": "Updated content."},
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data["title"], "Updated title")

        delete = self.client.delete(f"/api/posts/{post.id}/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Post.objects.filter(pk=post.id).exists())

    def test_non_author_cannot_edit_post(self):
        post = self.make_post()
        self.client.force_authenticate(user=self.outsider)

        response = self.client.patch(
            f"/api/posts/{post.id}/",
            {"title": "Hijacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_cannot_be_moved_to_another_community(self):
        post = self.make_post()
        other = Community.objects.create(
            name="Another Community",
            description="A different space.",
            owner=self.owner,
            visibility=Community.Visibility.PUBLIC,
        )
        CommunityMembership.objects.create(
            community=other,
            user=self.member,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.member)

        response = self.client.patch(
            f"/api/posts/{post.id}/",
            {"community_id": other.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("community_id", response.data)
        post.refresh_from_db()
        self.assertEqual(post.community_id, self.public.id)
