from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Comment(TimeStampedModel):
    """A threaded response to a post."""

    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField(max_length=4000)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "created_at"])]

    def __str__(self):
        return f"Comment by {self.author} on {self.post_id}"


class Reaction(TimeStampedModel):
    """One reaction per user per post, with a small set of meanings."""

    class Type(models.TextChoices):
        LIKE = "like", "Like"
        INSIGHTFUL = "insightful", "Insightful"
        HELPFUL = "helpful", "Helpful"

    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.LIKE)

    class Meta:
        unique_together = [("post", "user")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} → {self.post_id} ({self.type})"
