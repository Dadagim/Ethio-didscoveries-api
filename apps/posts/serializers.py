from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.models import Tag
from apps.accounts.serializers import UserSummarySerializer
from apps.communities.models import Community
from apps.communities.serializers import can_manage, is_active_member
from apps.media.models import MediaAsset
from apps.media.serializers import MediaAttachmentSerializer
from apps.media.services import (
    UnsupportedVideoURLError,
    attach_external_video,
    parse_youtube_url,
    remove_external_videos,
)

from .models import Post

VIDEO_POST_TYPES = {Post.Type.RESEARCH, Post.Type.PROJECT}


def resolve_tags(names):
    tags = []
    seen = set()
    for raw_name in names:
        name = raw_name.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        tag, _ = Tag.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name},
        )
        tags.append(tag)
    return tags


class PostCommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ["id", "name", "slug", "visibility", "category"]


class PostSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    community = PostCommunitySerializer(read_only=True)
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    tags = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    reaction_count = serializers.SerializerMethodField()
    reaction_summary = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_comment = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "content",
            "type",
            "type_label",
            "author",
            "community",
            "tags",
            "media",
            "comment_count",
            "reaction_count",
            "reaction_summary",
            "my_reaction",
            "can_edit",
            "can_comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_tags(self, obj):
        return [{"id": tag.id, "name": tag.name, "slug": tag.slug} for tag in obj.tags.all()]

    def get_media(self, obj):
        # Accessing .all() reuses the prefetched attachments when the view
        # supplies them, so a feed does not issue a query per post.
        return MediaAttachmentSerializer(obj.media_attachments.all(), many=True).data

    def get_comment_count(self, obj):
        annotated = getattr(obj, "comment_count", None)
        return annotated if annotated is not None else obj.comments.count()

    def get_reaction_count(self, obj):
        annotated = getattr(obj, "reaction_count", None)
        return annotated if annotated is not None else obj.reactions.count()

    def get_reaction_summary(self, obj):
        if hasattr(obj, "like_count"):
            return {
                "like": obj.like_count,
                "insightful": obj.insightful_count,
                "helpful": obj.helpful_count,
            }
        summary = {"like": 0, "insightful": 0, "helpful": 0}
        for reaction in obj.reactions.all():
            summary[reaction.type] = summary.get(reaction.type, 0) + 1
        return summary

    def get_my_reaction(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        prefetched = getattr(obj, "my_reactions", None)
        if prefetched is not None:
            reaction = prefetched[0] if prefetched else None
        else:
            reaction = obj.reactions.filter(user=request.user).first()

        return reaction.type if reaction else None

    def get_can_edit(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if not request.user.email_verified:
            return False
        return obj.author_id == request.user.id or can_manage(obj.community, request.user)

    def get_can_comment(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if not request.user.email_verified:
            return False
        return is_active_member(obj.community, request.user)


class PostWriteSerializer(serializers.ModelSerializer):
    community_id = serializers.PrimaryKeyRelatedField(
        source="community",
        queryset=Community.objects.all(),
        write_only=True,
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True,
        required=False,
    )
    video_url = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=500,
    )

    class Meta:
        model = Post
        fields = ["title", "content", "type", "community_id", "tags", "video_url"]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A title is required.")
        return value

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Content is required.")
        return value

    def validate(self, attrs):
        community = attrs.get("community")
        if self.instance and community and community.pk != self.instance.community_id:
            raise serializers.ValidationError(
                {
                    "community_id": (
                        "A contribution cannot be moved to another community. "
                        "Create a new contribution instead."
                    )
                }
            )

        post_type = attrs.get(
            "type",
            self.instance.type if self.instance else Post.Type.DISCUSSION,
        )
        video_url = attrs.get("video_url")
        if video_url:
            if post_type not in VIDEO_POST_TYPES:
                raise serializers.ValidationError(
                    {
                        "video_url": (
                            "Videos can only be attached to research or project "
                            "contributions."
                        )
                    }
                )
            try:
                parse_youtube_url(video_url)
            except UnsupportedVideoURLError as exc:
                raise serializers.ValidationError({"video_url": str(exc)}) from exc
        elif (
            self.instance
            and post_type not in VIDEO_POST_TYPES
            and "video_url" not in attrs
            and self.instance.media_attachments.filter(
                asset__kind=MediaAsset.Kind.EXTERNAL_VIDEO
            ).exists()
        ):
            raise serializers.ValidationError(
                {
                    "type": (
                        "Remove the video (send an empty video_url) before changing "
                        "to a text-only contribution type."
                    )
                }
            )
        return attrs

    def validate_community_id(self, community):
        request = self.context.get("request")
        if not request or not is_active_member(community, request.user):
            raise serializers.ValidationError(
                "You must be an active member of this community to publish."
            )
        return community

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        video_url = validated_data.pop("video_url", "")
        with transaction.atomic():
            post = Post.objects.create(
                author=self.context["request"].user,
                **validated_data,
            )
            post.tags.set(resolve_tags(tags))
            if video_url:
                attach_external_video(post, video_url, title=post.title)
        return post

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        video_url = validated_data.pop("video_url", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if tags is not None:
                instance.tags.set(resolve_tags(tags))
            if video_url is not None:
                remove_external_videos(instance)
                if video_url:
                    attach_external_video(instance, video_url, title=instance.title)
        return instance
