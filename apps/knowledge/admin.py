from django.contrib import admin

from .models import KnowledgeEntry, KnowledgeFolder


@admin.register(KnowledgeFolder)
class KnowledgeFolderAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    search_fields = ["name", "description", "owner__username"]
    autocomplete_fields = ["owner"]


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = ["title", "folder", "owner", "created_at"]
    list_filter = ["folder", "created_at"]
    search_fields = ["title", "content", "owner__username"]
    autocomplete_fields = ["owner", "folder"]
