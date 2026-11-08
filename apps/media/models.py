from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class MediaAsset(TimeStampedModel):
    """A reusable media record.

    The file or external provider owns the bytes; this model owns the identity,
    provenance, and safe playback information. Permissions are always derived
    from the object a ``MediaAttachment`` points at.
    """

    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        AUDIO = "audio", "Audio"
        VIDEO = "video", "Video"
        DOCUMENT = "document", "Document"
        EXTERNAL_VIDEO = "external_video", "External video"

    class Source(models.TextChoices):
        UPLOAD = "upload", "Upload"
        EXTERNAL = "external", "External provider"

    class Provider(models.TextChoices):
        YOUTUBE = "youtube", "YouTube"
        INTERNAL = "internal", "Internal storage"

    class Status(models.TextChoices):
        READY = "ready", "Ready"
        PROCESSING = "processing", "Processing"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="media_assets",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.IMAGE)
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.UPLOAD,
    )
    provider = models.CharField(
        max_length=32,
        choices=Provider.choices,
        blank=True,
    )
    external_id = models.CharField(max_length=64, blank=True)
    canonical_url = models.URLField(max_length=500)
    embed_url = models.URLField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    title = models.CharField(max_length=200, blank=True)
    storage_key = models.CharField(max_length=500, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.READY)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                condition=Q(source="external"),
                name="unique_external_media_provider_id",
            )
        ]
        indexes = [
            models.Index(fields=["provider", "external_id"]),
        ]

    def __str__(self):
        label = self.title or self.external_id or self.pk
        return f"{self.provider or 'internal'} · {label}"


class MediaAttachment(TimeStampedModel):
    """Links one media asset to any domain object with a role and order."""

    class Role(models.TextChoices):
        EXPLANATION = "explanation", "Explanation"
        SETUP = "setup", "Setup"
        PROCEDURE = "procedure", "Procedure"
        OBSERVATION = "observation", "Observation"
        RESULT = "result", "Result"
        SUPPORTING = "supporting", "Supporting material"
        REFERENCE = "reference", "Reference"

    asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.REFERENCE,
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "content_type", "object_id"],
                name="unique_media_attachment",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.asset} → {self.content_type.model}:{self.object_id}"
