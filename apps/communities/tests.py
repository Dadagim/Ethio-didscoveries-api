from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Community, CommunityMembership

User = get_user_model()


class CommunityTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="SecurePass!2026",
            email_verified=True,
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="SecurePass!2026",
            email_verified=True,
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="SecurePass!2026",
            email_verified=True,
        )

    def create_community(self, **overrides):
        data = {
            "name": "Renewable Energy",
            "description": "Solar, wind, and storage research.",
            "purpose": "Make clean energy affordable.",
            "category": Community.Category.PROBLEM,
            "visibility": Community.Visibility.PUBLIC,
        }
        data.update(overrides)
        self.client.force_authenticate(user=self.owner)
        response = self.client.post("/api/communities/", data, format="json")
        self.client.force_authenticate(user=None)
        return response


class CommunityCreationTests(CommunityTestCase):
    def test_create_community_makes_creator_owner(self):
        response = self.create_community()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        community = Community.objects.get(slug=response.data["slug"])
        self.assertEqual(community.owner, self.owner)
        membership = community.memberships.get(user=self.owner)
        self.assertEqual(membership.role, CommunityMembership.Role.OWNER)
        self.assertEqual(membership.status, CommunityMembership.Status.ACTIVE)
        self.assertIsNotNone(membership.joined_at)
        self.assertEqual(response.data["member_count"], 1)

    def test_create_requires_authentication(self):
        response = self.client.post(
            "/api/communities/",
            {"name": "Robotics", "description": "Robots."},
            format="json",
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_duplicate_name_is_rejected_case_insensitively(self):
        self.create_community()
        response = self.create_community(name="renewable energy")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)


class CommunityVisibilityTests(CommunityTestCase):
    def test_public_and_restricted_are_listed_but_private_is_not(self):
        public = self.create_community(name="Public Lab")
        restricted = self.create_community(
            name="Restricted Lab",
            visibility=Community.Visibility.RESTRICTED,
        )
        private = self.create_community(
            name="Private Lab",
            visibility=Community.Visibility.PRIVATE,
        )

        response = self.client.get("/api/communities/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn(public.data["name"], names)
        self.assertIn(restricted.data["name"], names)
        self.assertNotIn(private.data["name"], names)

    def test_private_community_detail_is_hidden_from_outsiders(self):
        private = self.create_community(
            name="Secret Lab",
            visibility=Community.Visibility.PRIVATE,
        )

        response = self.client.get(f"/api/communities/{private.data['slug']}/")

        # Private communities return 404 so outsiders cannot confirm they exist.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_private_community_is_visible_to_members(self):
        private = self.create_community(
            name="Member Lab",
            visibility=Community.Visibility.PRIVATE,
        )
        community = Community.objects.get(slug=private.data["slug"])
        CommunityMembership.objects.create(
            community=community,
            user=self.member,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(f"/api/communities/{community.slug}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["membership"]["status"] == "active")


class CommunityMembershipTests(CommunityTestCase):
    def test_public_join_is_immediate(self):
        community = Community.objects.get(
            slug=self.create_community().data["slug"]
        )
        self.client.force_authenticate(user=self.member)

        response = self.client.post(f"/api/communities/{community.slug}/join/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership = community.memberships.get(user=self.member)
        self.assertEqual(membership.status, CommunityMembership.Status.ACTIVE)
        self.assertEqual(response.data["membership"]["status"], "active")

    def test_restricted_join_requires_approval(self):
        community = Community.objects.get(
            slug=self.create_community(
                visibility=Community.Visibility.RESTRICTED
            ).data["slug"]
        )
        self.client.force_authenticate(user=self.member)

        join_response = self.client.post(f"/api/communities/{community.slug}/join/")
        self.assertEqual(join_response.data["membership"]["status"], "pending")

        pending_response = self.client.get(
            f"/api/communities/{community.slug}/members/?status=pending"
        )
        self.assertEqual(pending_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.owner)
        pending_response = self.client.get(
            f"/api/communities/{community.slug}/members/?status=pending"
        )
        self.assertEqual(pending_response.status_code, status.HTTP_200_OK)
        membership_id = pending_response.data["results"][0]["id"]

        approve_response = self.client.post(
            f"/api/communities/{community.slug}/members/{membership_id}/approve/"
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_response.data["status"], "active")

    def test_member_can_leave_but_owner_cannot(self):
        community = Community.objects.get(
            slug=self.create_community().data["slug"]
        )

        self.client.force_authenticate(user=self.member)
        self.client.post(f"/api/communities/{community.slug}/join/")
        leave_response = self.client.post(f"/api/communities/{community.slug}/leave/")
        self.assertEqual(leave_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(community.memberships.filter(user=self.member).exists())

        self.client.force_authenticate(user=self.owner)
        owner_leave = self.client.post(f"/api/communities/{community.slug}/leave/")
        self.assertEqual(owner_leave.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_managers_can_edit_community(self):
        community = Community.objects.get(
            slug=self.create_community().data["slug"]
        )

        self.client.force_authenticate(user=self.outsider)
        response = self.client.patch(
            f"/api/communities/{community.slug}/",
            {"description": "Hijacked."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            f"/api/communities/{community.slug}/",
            {"description": "Updated by the owner."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "Updated by the owner.")

    def test_owner_can_delete_community(self):
        community = Community.objects.get(
            slug=self.create_community().data["slug"]
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(f"/api/communities/{community.slug}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Community.objects.filter(pk=community.pk).exists())
