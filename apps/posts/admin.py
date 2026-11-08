from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "community", "author", "type", "created_at"]
    list_filter = ["type", "community", "created_at"]
    search_fields = ["title", "content", "author__username"]
    autocomplete_fields = ["community", "author"]
    filter_horizontal = ["tags"]
