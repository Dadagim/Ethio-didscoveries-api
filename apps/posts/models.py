from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.common.models import TimeStampedModel


class Post(TimeStampedModel):
    """A contribution shared inside a community."""

    class Type(models.TextChoices):
        DISCUSSION = "discussion", "Discussion"
        QUESTION = "question", "Question"
        PROBLEM = "problem", "Problem"
        IDEA = "idea", "Idea"
        RESEARCH = "research", "Research"
        PROJECT = "project", "Project"

    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.CASCADE,
        related_name="posts",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    title = models.CharField(max_length=240)
    content = models.TextField(max_length=12000)
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.DISCUSSION,
    )
    tags = models.ManyToManyField(
        "accounts.Tag",
        blank=True,
        related_name="posts",
    )
    media_attachments = GenericRelation(
        "media.MediaAttachment",
        related_query_name="post",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["community", "-created_at"]),
            models.Index(fields=["type", "-created_at"]),
        ]

    def __str__(self):
        return self.title
