from rest_framework import serializers

from .models import MediaAttachment


class MediaAttachmentSerializer(serializers.ModelSerializer):
    """Read-only playback data for an attached asset."""

    kind = serializers.CharField(source="asset.kind", read_only=True)
    source = serializers.CharField(source="asset.source", read_only=True)
    provider = serializers.CharField(source="asset.provider", read_only=True)
    external_id = serializers.CharField(source="asset.external_id", read_only=True)
    canonical_url = serializers.URLField(source="asset.canonical_url", read_only=True)
    embed_url = serializers.URLField(source="asset.embed_url", read_only=True)
    thumbnail_url = serializers.URLField(source="asset.thumbnail_url", read_only=True)
    title = serializers.CharField(source="asset.title", read_only=True)
    duration_seconds = serializers.IntegerField(
        source="asset.duration_seconds",
        read_only=True,
    )

    class Meta:
        model = MediaAttachment
        fields = [
            "id",
            "role",
            "position",
            "kind",
            "source",
            "provider",
            "external_id",
            "canonical_url",
            "embed_url",
            "thumbnail_url",
            "title",
            "duration_seconds",
        ]
        read_only_fields = fields
