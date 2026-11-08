from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified

from .models import Community, CommunityMembership
from .serializers import (
    CommunitySerializer,
    CommunityWriteSerializer,
    MemberSerializer,
    can_manage,
    can_view,
    join_community,
    membership_for,
)


def visible_communities(user):
    queryset = Community.objects.select_related("owner").annotate(
        member_count=Count(
            "memberships",
            filter=Q(memberships__status=CommunityMembership.Status.ACTIVE),
            distinct=True,
        )
    )

    if not user.is_authenticated:
        return queryset.filter(
            visibility__in=[
                Community.Visibility.PUBLIC,
                Community.Visibility.RESTRICTED,
            ]
        )

    if user.is_staff:
        return queryset

    return queryset.filter(
        Q(visibility__in=[Community.Visibility.PUBLIC, Community.Visibility.RESTRICTED])
        | Q(
            memberships__user=user,
            memberships__status__in=[
                CommunityMembership.Status.ACTIVE,
                CommunityMembership.Status.PENDING,
            ],
        )
    ).distinct()


def with_my_membership(queryset, user):
    if not user.is_authenticated:
        return queryset
    return queryset.prefetch_related(
        Prefetch(
            "memberships",
            queryset=CommunityMembership.objects.filter(user=user).select_related("user"),
            to_attr="my_memberships",
        )
    )


class CommunityListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "GET":
            return []
        return [IsAuthenticated(), IsEmailVerified()]

    def get_queryset(self):
        queryset = with_my_membership(visible_communities(self.request.user), self.request.user)

        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(purpose__icontains=search)
            )

        category = self.request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category=category)

        membership_filter = self.request.query_params.get("membership", "").strip()
        if membership_filter == "joined" and self.request.user.is_authenticated:
            queryset = queryset.filter(
                memberships__user=self.request.user,
                memberships__status=CommunityMembership.Status.ACTIVE,
            )

        return queryset.order_by("name")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommunityWriteSerializer
        return CommunitySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        community = serializer.save(owner=request.user)
        CommunityMembership.objects.create(
            community=community,
            user=request.user,
            role=CommunityMembership.Role.OWNER,
            status=CommunityMembership.Status.ACTIVE,
            joined_at=timezone.now(),
        )
        community = with_my_membership(
            visible_communities(request.user).filter(pk=community.pk),
            request.user,
        ).get()
        return Response(
            CommunitySerializer(community, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CommunityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "GET":
            return []
        return [IsAuthenticated()]

    def get_community(self, request, slug):
        community = get_object_or_404(
            with_my_membership(visible_communities(request.user), request.user),
            slug=slug,
        )
        if not can_view(community, request.user):
            raise PermissionDenied("You do not have access to this community.")
        return community

    def get(self, request, slug):
        community = self.get_community(request, slug)
        data = CommunitySerializer(community, context={"request": request}).data
        membership = membership_for(community, request.user)
        data["can_manage"] = bool(membership and membership.can_manage)
        return Response(data)

    def patch(self, request, slug):
        community = get_object_or_404(Community, slug=slug)
        if not can_manage(community, request.user):
            raise PermissionDenied("Only owners and moderators can edit this community.")

        serializer = CommunityWriteSerializer(community, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        community = with_my_membership(
            visible_communities(request.user).filter(pk=community.pk),
            request.user,
        ).get()
        return Response(
            CommunitySerializer(community, context={"request": request}).data
        )

    def delete(self, request, slug):
        community = get_object_or_404(Community, slug=slug)
        if community.owner_id != request.user.id:
            raise PermissionDenied("Only the owner can delete this community.")
        community.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommunityJoinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        community = get_object_or_404(Community, slug=slug)
        if not can_view(community, request.user):
            raise PermissionDenied("You do not have access to this community.")

        membership = join_community(community, request.user)
        community = with_my_membership(
            visible_communities(request.user).filter(pk=community.pk),
            request.user,
        ).get()
        return Response(
            {
                "membership": MemberSerializer(membership).data,
                "community": CommunitySerializer(
                    community, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class CommunityLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        community = get_object_or_404(Community, slug=slug)
        membership = community.memberships.filter(user=request.user).first()
        if membership is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if membership.role == CommunityMembership.Role.OWNER:
            return Response(
                {"detail": "The owner cannot leave. Delete the community or transfer ownership first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommunityMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        community = get_object_or_404(Community, slug=slug)
        if not can_view(community, request.user):
            raise PermissionDenied("You do not have access to this community.")

        membership = membership_for(community, request.user)
        manager = bool(membership and membership.can_manage)

        requested_status = request.query_params.get("status", "").strip()
        if requested_status == CommunityMembership.Status.PENDING and not manager:
            raise PermissionDenied("Only owners and moderators can view pending requests.")

        memberships = community.memberships.select_related("user", "user__profile")
        if requested_status:
            memberships = memberships.filter(status=requested_status)
        elif not manager:
            memberships = memberships.filter(status=CommunityMembership.Status.ACTIVE)

        return Response(
            {
                "count": memberships.count(),
                "results": MemberSerializer(memberships, many=True).data,
            }
        )


class CommunityMembershipModerationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, membership_id, action):
        community = get_object_or_404(Community, slug=slug)
        if not can_manage(community, request.user):
            raise PermissionDenied("Only owners and moderators can review requests.")

        membership = get_object_or_404(
            community.memberships.select_related("user"),
            pk=membership_id,
        )
        if membership.role == CommunityMembership.Role.OWNER:
            return Response(
                {"detail": "The owner's membership cannot be moderated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if membership.status != CommunityMembership.Status.PENDING:
            return Response(
                {"detail": "Only pending requests can be reviewed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == "approve":
            membership.status = CommunityMembership.Status.ACTIVE
            membership.joined_at = timezone.now()
        elif action == "reject":
            membership.status = CommunityMembership.Status.REJECTED
        else:
            return Response(
                {"detail": "Unknown moderation action."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.save(update_fields=["status", "joined_at", "updated_at"])
        return Response(MemberSerializer(membership).data)
