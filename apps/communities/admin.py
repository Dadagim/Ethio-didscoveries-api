from django.contrib import admin

from .models import Community, CommunityMembership


class CommunityMembershipInline(admin.TabularInline):
    model = CommunityMembership
    extra = 0
    autocomplete_fields = ["user"]
    fields = ["user", "role", "status", "joined_at"]


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "visibility", "owner", "created_at"]
    list_filter = ["category", "visibility"]
    search_fields = ["name", "description", "purpose", "owner__username"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["owner"]
    inlines = [CommunityMembershipInline]


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ["community", "user", "role", "status", "joined_at"]
    list_filter = ["role", "status"]
    search_fields = ["community__name", "user__username"]
    autocomplete_fields = ["community", "user"]
