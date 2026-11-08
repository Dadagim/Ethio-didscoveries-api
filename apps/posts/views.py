from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.communities.models import Community
from apps.communities.serializers import can_manage, can_view_content
from apps.interactions.models import Reaction

from .models import Post
from .serializers import PostSerializer, PostWriteSerializer


def visible_posts(user):
    queryset = Post.objects.select_related(
        "author", "author__profile", "community"
    ).prefetch_related(
        "tags",
        "community__memberships",
        "media_attachments__asset",
    )

    if user.is_authenticated and user.is_staff:
        pass
    elif user.is_authenticated:
        queryset = queryset.filter(
            Q(community__visibility=Community.Visibility.PUBLIC)
            | Q(
                community__memberships__user=user,
                community__memberships__status="active",
            )
        ).distinct()
    else:
        queryset = queryset.filter(
            community__visibility=Community.Visibility.PUBLIC
        )

    queryset = queryset.annotate(
        comment_count=Count("comments", distinct=True),
        reaction_count=Count("reactions", distinct=True),
        like_count=Count(
            "reactions",
            filter=Q(reactions__type=Reaction.Type.LIKE),
            distinct=True,
        ),
        insightful_count=Count(
            "reactions",
            filter=Q(reactions__type=Reaction.Type.INSIGHTFUL),
            distinct=True,
        ),
        helpful_count=Count(
            "reactions",
            filter=Q(reactions__type=Reaction.Type.HELPFUL),
            distinct=True,
        ),
    )

    if user.is_authenticated:
        queryset = queryset.prefetch_related(
            Prefetch(
                "reactions",
                queryset=Reaction.objects.filter(user=user),
                to_attr="my_reactions",
            )
        )

    return queryset


def annotated_post(post_id, user):
    return visible_posts(user).get(pk=post_id)


class PostListCreateView(generics.ListCreateAPIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return []
        return [IsAuthenticated(), IsEmailVerified()]

    def get_queryset(self):
        queryset = visible_posts(self.request.user)
        params = self.request.query_params

        community = params.get("community", "").strip()
        if community:
            queryset = queryset.filter(community__slug=community)

        post_type = params.get("type", "").strip()
        if post_type:
            types = [item.strip() for item in post_type.split(",") if item.strip()]
            if types:
                queryset = queryset.filter(type__in=types)

        author = params.get("author", "").strip()
        if author:
            queryset = queryset.filter(author__username__iexact=author)

        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        ordering = params.get("ordering", "-created_at").strip()
        allowed = {"created_at", "-created_at", "updated_at", "-updated_at"}
        return queryset.order_by(ordering if ordering in allowed else "-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PostWriteSerializer
        return PostSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = serializer.save()
        post = annotated_post(post.pk, request.user)
        return Response(
            PostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PostDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return []
        return [IsAuthenticated(), IsEmailVerified()]

    def get_object(self, request, pk):
        post = get_object_or_404(visible_posts(request.user), pk=pk)
        if not can_view_content(post.community, request.user):
            raise PermissionDenied("You do not have access to this post.")
        return post

    def get(self, request, pk):
        post = self.get_object(request, pk)
        return Response(PostSerializer(post, context={"request": request}).data)

    def _assert_can_edit(self, post, user):
        if post.author_id != user.id and not can_manage(post.community, user):
            raise PermissionDenied("Only the author or a community manager can edit this post.")

    def patch(self, request, pk):
        post = self.get_object(request, pk)
        self._assert_can_edit(post, request.user)
        serializer = PostWriteSerializer(
            post,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        post = annotated_post(post.pk, request.user)
        return Response(PostSerializer(post, context={"request": request}).data)

    def delete(self, request, pk):
        post = self.get_object(request, pk)
        self._assert_can_edit(post, request.user)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
