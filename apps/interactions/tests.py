from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.communities.models import Community, CommunityMembership
from apps.posts.models import Post

from .models import Comment, Reaction

User = get_user_model()


class InteractionTestCase(APITestCase):
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
        CommunityMembership.objects.create(
            community=self.community,
            user=self.member,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        self.post = Post.objects.create(
            community=self.community,
            author=self.member,
            title="A shared question",
            content="How should we test this?",
            type=Post.Type.QUESTION,
        )


class CommentTests(InteractionTestCase):
    def test_active_member_can_comment_and_anonymous_can_read(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            f"/api/posts/{self.post.id}/comments/",
            {"body": "We could start with a small pilot."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author"]["username"], "member")

        self.client.force_authenticate(user=None)
        listing = self.client.get(f"/api/posts/{self.post.id}/comments/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["body"], "We could start with a small pilot.")

    def test_non_member_cannot_comment(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            f"/api/posts/{self.post.id}/comments/",
            {"body": "Let me in."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unverified_member_cannot_comment(self):
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
            f"/api/posts/{self.post.id}/comments/",
            {"body": "Not yet verified."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_not_verified")

    def test_replies_are_one_level_deep(self):
        self.client.force_authenticate(user=self.member)
        parent = self.client.post(
            f"/api/posts/{self.post.id}/comments/",
            {"body": "Parent comment."},
            format="json",
        )
        reply = self.client.post(
            f"/api/posts/{self.post.id}/comments/",
            {"body": "A reply.", "parent_id": parent.data["id"]},
            format="json",
        )
        self.assertEqual(reply.status_code, status.HTTP_201_CREATED)

        deep_reply = self.client.post(
            f"/api/posts/{self.post.id}/comments/",
            {"body": "Too deep.", "parent_id": reply.data["id"]},
            format="json",
        )
        self.assertEqual(deep_reply.status_code, status.HTTP_400_BAD_REQUEST)

        listing = self.client.get(f"/api/posts/{self.post.id}/comments/")
        self.assertEqual(len(listing.data["results"]), 1)
        self.assertEqual(len(listing.data["results"][0]["replies"]), 1)

    def test_comment_owner_and_manager_can_delete(self):
        comment = Comment.objects.create(
            post=self.post,
            author=self.member,
            body="Temporary.",
        )
        self.client.force_authenticate(user=self.outsider)
        forbidden = self.client.delete(f"/api/comments/{comment.id}/")
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.owner)
        deleted = self.client.delete(f"/api/comments/{comment.id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Comment.objects.filter(pk=comment.id).exists())


class ReactionTests(InteractionTestCase):
    def test_reaction_add_change_and_remove(self):
        self.client.force_authenticate(user=self.member)

        added = self.client.post(
            f"/api/posts/{self.post.id}/react/",
            {"type": "like"},
            format="json",
        )
        self.assertEqual(added.status_code, status.HTTP_200_OK)
        self.assertEqual(added.data["action"], "added")
        self.assertEqual(added.data["reaction_summary"]["like"], 1)
        self.assertEqual(added.data["my_reaction"], "like")

        changed = self.client.post(
            f"/api/posts/{self.post.id}/react/",
            {"type": "insightful"},
            format="json",
        )
        self.assertEqual(changed.data["action"], "updated")
        self.assertEqual(changed.data["reaction_summary"]["insightful"], 1)
        self.assertEqual(changed.data["reaction_summary"]["like"], 0)

        removed = self.client.post(
            f"/api/posts/{self.post.id}/react/",
            {"type": "insightful"},
            format="json",
        )
        self.assertEqual(removed.data["action"], "removed")
        self.assertEqual(removed.data["reaction_count"], 0)
        self.assertFalse(Reaction.objects.filter(post=self.post).exists())

    def test_invalid_reaction_type_is_rejected(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            f"/api/posts/{self.post.id}/react/",
            {"type": "clap"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reaction_requires_authentication(self):
        response = self.client.post(
            f"/api/posts/{self.post.id}/react/",
            {"type": "like"},
            format="json",
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_unverified_user_cannot_react(self):
        unverified = User.objects.create_user(
            username="unverified",
            email="unverified@example.com",
            password="SecurePass!2026",
        )
        self.client.force_authenticate(user=unverified)

        response = self.client.post(
            f"/api/posts/{self.post.id}/react/",
            {"type": "like"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "email_not_verified")
