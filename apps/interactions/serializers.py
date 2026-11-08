from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.communities.serializers import can_manage

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "body",
            "author",
            "parent",
            "replies",
            "can_delete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_replies(self, obj):
        replies = getattr(obj, "prefetched_replies", None)
        if replies is None:
            replies = obj.replies.select_related("author", "author__profile").all()
        return CommentSerializer(replies, many=True, context=self.context).data

    def get_can_delete(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.author_id == request.user.id or can_manage(obj.post.community, request.user)


class CommentWriteSerializer(serializers.ModelSerializer):
    parent_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Comment
        fields = ["body", "parent_id"]

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A comment cannot be empty.")
        return value

    def validate(self, attrs):
        parent_id = attrs.pop("parent_id", None)
        if parent_id is None:
            attrs["parent"] = None
            return attrs

        post = self.context["post"]
        parent = post.comments.filter(pk=parent_id).first()
        if parent is None:
            raise serializers.ValidationError({"parent_id": "That comment does not exist."})
        if parent.parent_id is not None:
            raise serializers.ValidationError(
                {"parent_id": "Replies can only be one level deep."}
            )
        attrs["parent"] = parent
        return attrs

    def create(self, validated_data):
        return Comment.objects.create(
            post=self.context["post"],
            author=self.context["request"].user,
            **validated_data,
        )
