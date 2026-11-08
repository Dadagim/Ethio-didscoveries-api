from rest_framework import serializers

from .models import KnowledgeEntry, KnowledgeFolder


class KnowledgeFolderSerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeFolder
        fields = [
            "id",
            "name",
            "description",
            "entry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "entry_count", "created_at", "updated_at"]

    def get_entry_count(self, obj):
        annotated = getattr(obj, "entry_count", None)
        return annotated if annotated is not None else obj.entries.count()

    def validate_name(self, value):
        value = value.strip()
        request = self.context.get("request")
        if not value:
            raise serializers.ValidationError("A folder name is required.")
        queryset = KnowledgeFolder.objects.filter(
            owner=request.user,
            name__iexact=value,
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("You already have a folder with that name.")
        return value


class KnowledgeEntrySerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(source="folder.name", read_only=True)

    class Meta:
        model = KnowledgeEntry
        fields = [
            "id",
            "folder",
            "folder_name",
            "title",
            "content",
            "source_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "folder_name", "created_at", "updated_at"]

    def validate_folder(self, folder):
        request = self.context.get("request")
        if not request or folder.owner_id != request.user.id:
            raise serializers.ValidationError("Choose one of your own folders.")
        return folder

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A title is required.")
        return value

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Write the note you want to keep.")
        return value
