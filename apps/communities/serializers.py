from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Community, CommunityMembership


class CommunitySerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    visibility_label = serializers.CharField(source="get_visibility_display", read_only=True)
    member_count = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "purpose",
            "category",
            "category_label",
            "visibility",
            "visibility_label",
            "owner",
            "member_count",
            "membership",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_member_count(self, obj):
        annotated = getattr(obj, "member_count", None)
        if annotated is not None:
            return annotated
        return obj.memberships.filter(status=CommunityMembership.Status.ACTIVE).count()

    def get_membership(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        prefetched = getattr(obj, "my_memberships", None)
        if prefetched is not None:
            membership = prefetched[0] if prefetched else None
        else:
            membership = obj.memberships.filter(user=request.user).first()

        if membership is None:
            return None

        return {
            "id": membership.id,
            "role": membership.role,
            "role_label": membership.get_role_display(),
            "status": membership.status,
            "status_label": membership.get_status_display(),
            "can_manage": membership.can_manage,
        }


class CommunityWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ["name", "description", "purpose", "category", "visibility"]

    def validate_name(self, value):
        value = value.strip()
        queryset = Community.objects.filter(name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A community with that name already exists.")
        return value


class MemberSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CommunityMembership
        fields = [
            "id",
            "user",
            "role",
            "role_label",
            "status",
            "status_label",
            "joined_at",
        ]
        read_only_fields = fields


def membership_for(community, user):
    if not user.is_authenticated:
        return None
    return community.memberships.filter(user=user).first()


def can_view(community, user):
    if community.visibility != Community.Visibility.PRIVATE:
        return True
    if not user.is_authenticated:
        return False
    return community.memberships.filter(
        user=user,
        status__in=[
            CommunityMembership.Status.ACTIVE,
            CommunityMembership.Status.PENDING,
        ],
    ).exists()


def can_manage(community, user):
    if not user.is_authenticated:
        return False
    return community.memberships.filter(
        user=user,
        status=CommunityMembership.Status.ACTIVE,
        role__in=[CommunityMembership.Role.OWNER, CommunityMembership.Role.MODERATOR],
    ).exists()


def is_active_member(community, user):
    if not user.is_authenticated:
        return False
    return community.memberships.filter(
        user=user,
        status=CommunityMembership.Status.ACTIVE,
    ).exists()


def can_view_content(community, user):
    """Only active members can read restricted or private community content."""

    if user.is_authenticated and user.is_staff:
        return True
    if community.visibility == Community.Visibility.PUBLIC:
        return True
    return is_active_member(community, user)


def join_community(community, user):
    """Create or refresh a membership according to the community's visibility."""

    membership = community.memberships.filter(user=user).first()
    status = (
        CommunityMembership.Status.ACTIVE
        if community.visibility == Community.Visibility.PUBLIC
        else CommunityMembership.Status.PENDING
    )
    role = CommunityMembership.Role.MEMBER

    if membership is None:
        membership = CommunityMembership.objects.create(
            community=community,
            user=user,
            role=role,
            status=status,
            joined_at=timezone.now() if status == CommunityMembership.Status.ACTIVE else None,
        )
        return membership

    if membership.status == CommunityMembership.Status.ACTIVE:
        return membership

    membership.status = status
    if status == CommunityMembership.Status.ACTIVE:
        membership.joined_at = timezone.now()
    membership.save(update_fields=["status", "joined_at", "updated_at"])
    return membership
