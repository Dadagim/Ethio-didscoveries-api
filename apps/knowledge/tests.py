from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import KnowledgeEntry, KnowledgeFolder

User = get_user_model()


class KnowledgeTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="SecurePass!2026"
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="SecurePass!2026"
        )
        self.client.force_authenticate(user=self.owner)

    def create_folder(self, name="Energy notes", owner=None):
        return KnowledgeFolder.objects.create(
            owner=owner or self.owner,
            name=name,
            description="Things worth remembering.",
        )

    def entry_payload(self, folder=None, **overrides):
        payload = {
            "folder": (folder or self.create_folder()).id,
            "title": "Battery sizing rule of thumb",
            "content": "Size the battery for two cloudy days, then check the depth of discharge.",
            "source_url": "https://example.org/battery-sizing",
        }
        payload.update(overrides)
        return payload


class KnowledgeFolderTests(KnowledgeTestCase):
    def test_create_folder_is_private_to_owner(self):
        response = self.client.post(
            "/api/knowledge/folders/",
            {"name": "Methods", "description": "Research methods"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        folder = KnowledgeFolder.objects.get(pk=response.data["id"])
        self.assertEqual(folder.owner, self.owner)
        self.assertEqual(response.data["entry_count"], 0)

    def test_duplicate_folder_name_is_rejected_for_same_owner(self):
        self.create_folder(name="Methods")

        response = self.client.post(
            "/api/knowledge/folders/",
            {"name": "methods"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_folders_are_never_listed_for_another_user(self):
        self.create_folder(name="Mine")
        self.create_folder(name="Theirs", owner=self.other)

        response = self.client.get("/api/knowledge/folders/")

        names = [folder["name"] for folder in response.data["results"]]
        self.assertEqual(names, ["Mine"])

    def test_folder_with_entries_cannot_be_deleted(self):
        folder = self.create_folder()
        KnowledgeEntry.objects.create(
            owner=self.owner,
            folder=folder,
            title="Saved note",
            content="Useful context.",
        )

        response = self.client.delete(f"/api/knowledge/folders/{folder.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(KnowledgeFolder.objects.filter(pk=folder.id).exists())

    def test_empty_folder_can_be_deleted(self):
        folder = self.create_folder()

        response = self.client.delete(f"/api/knowledge/folders/{folder.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(KnowledgeFolder.objects.filter(pk=folder.id).exists())


class KnowledgeEntryTests(KnowledgeTestCase):
    def test_create_entry_inside_own_folder(self):
        folder = self.create_folder()

        response = self.client.post(
            "/api/knowledge/entries/", self.entry_payload(folder), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = KnowledgeEntry.objects.get(pk=response.data["id"])
        self.assertEqual(entry.owner, self.owner)
        self.assertEqual(response.data["folder_name"], "Energy notes")

    def test_entry_cannot_use_another_users_folder(self):
        foreign_folder = self.create_folder(name="Not mine", owner=self.other)

        response = self.client.post(
            "/api/knowledge/entries/",
            self.entry_payload(foreign_folder),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("folder", response.data)

    def test_entries_are_isolated_by_owner_and_filter_by_folder(self):
        folder = self.create_folder()
        other_folder = self.create_folder(name="Other folder")
        own_entry = KnowledgeEntry.objects.create(
            owner=self.owner, folder=folder, title="Mine", content="Private."
        )
        KnowledgeEntry.objects.create(
            owner=self.owner, folder=other_folder, title="Second", content="Also mine."
        )
        KnowledgeEntry.objects.create(
            owner=self.other, folder=self.create_folder("Theirs", self.other),
            title="Theirs", content="Not mine.",
        )

        response = self.client.get(f"/api/knowledge/entries/?folder={folder.id}")

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], own_entry.id)

    def test_other_user_cannot_read_or_change_entry(self):
        entry = KnowledgeEntry.objects.create(
            owner=self.owner,
            folder=self.create_folder(),
            title="Private note",
            content="Only the owner should see this.",
        )
        self.client.force_authenticate(user=self.other)

        read = self.client.get(f"/api/knowledge/entries/{entry.id}/")
        update = self.client.patch(
            f"/api/knowledge/entries/{entry.id}/",
            {"title": "Hijacked"},
            format="json",
        )
        delete = self.client.delete(f"/api/knowledge/entries/{entry.id}/")

        self.assertEqual(read.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(update.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(KnowledgeEntry.objects.filter(pk=entry.id).exists())

    def test_owner_can_update_and_delete_entry(self):
        entry = KnowledgeEntry.objects.create(
            owner=self.owner,
            folder=self.create_folder(),
            title="Old title",
            content="Old content.",
        )

        update = self.client.patch(
            f"/api/knowledge/entries/{entry.id}/",
            {"title": "New title"},
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data["title"], "New title")

        delete = self.client.delete(f"/api/knowledge/entries/{entry.id}/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(KnowledgeEntry.objects.filter(pk=entry.id).exists())

    def test_search_matches_title_and_content(self):
        folder = self.create_folder()
        KnowledgeEntry.objects.create(
            owner=self.owner, folder=folder, title="Solar sizing", content="Panels."
        )
        KnowledgeEntry.objects.create(
            owner=self.owner, folder=folder, title="Interview notes", content="Battery chemistry."
        )

        response = self.client.get("/api/knowledge/entries/?search=battery")

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Interview notes")

    def test_anonymous_cannot_access_knowledge(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/knowledge/folders/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
