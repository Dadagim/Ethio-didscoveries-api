from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class KnowledgeFolder(TimeStampedModel):
    """A private folder that groups a person's learning entries."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_folders",
    )
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_knowledge_folder_name_per_owner",
            )
        ]

    def __str__(self):
        return f"{self.owner.username} · {self.name}"


class KnowledgeEntry(TimeStampedModel):
    """A private learning note kept by one person inside one folder."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_entries",
    )
    folder = models.ForeignKey(
        KnowledgeFolder,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    title = models.CharField(max_length=200)
    content = models.TextField(max_length=8000)
    source_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "knowledge entries"
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self):
        return self.title
