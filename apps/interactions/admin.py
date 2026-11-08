from django.contrib import admin

from .models import Comment, Reaction


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "post", "author", "parent", "created_at"]
    search_fields = ["body", "author__username", "post__title"]
    autocomplete_fields = ["post", "author", "parent"]


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ["post", "user", "type", "created_at"]
    list_filter = ["type"]
    search_fields = ["user__username", "post__title"]
    autocomplete_fields = ["post", "user"]
