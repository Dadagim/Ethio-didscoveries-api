from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.communities.serializers import can_manage, can_view_content, is_active_member
from apps.posts.views import visible_posts

from .models import Comment, Reaction
from .serializers import CommentSerializer, CommentWriteSerializer


def get_visible_post(request, pk):
    post = get_object_or_404(visible_posts(request.user), pk=pk)
    if not can_view_content(post.community, request.user):
        raise PermissionDenied("You do not have access to this post.")
    return post


def reaction_summary(post):
    summary = {"like": 0, "insightful": 0, "helpful": 0}
    rows = post.reactions.values("type").annotate(total=Count("id"))
    for row in rows:
        summary[row["type"]] = row["total"]
    return summary


class PostCommentsView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return []
        return [IsAuthenticated(), IsEmailVerified()]

    def get(self, request, pk):
        post = get_visible_post(request, pk)
        comments = (
            post.comments.filter(parent__isnull=True)
            .select_related("author", "author__profile")
            .prefetch_related(
                Prefetch(
                    "replies",
                    queryset=Comment.objects.select_related(
                        "author", "author__profile"
                    ).order_by("created_at"),
                    to_attr="prefetched_replies",
                )
            )
        )
        return Response(
            {
                "count": post.comments.count(),
                "results": CommentSerializer(
                    comments,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )

    def post(self, request, pk):
        post = get_visible_post(request, pk)
        if not is_active_member(post.community, request.user):
            raise PermissionDenied(
                "Join this community before taking part in the discussion."
            )

        serializer = CommentWriteSerializer(
            data=request.data,
            context={"request": request, "post": post},
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        comment = Comment.objects.select_related("author", "author__profile").get(
            pk=comment.pk
        )
        return Response(
            CommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        comment = get_object_or_404(
            Comment.objects.select_related("post", "post__community"),
            pk=pk,
        )
        if (
            comment.author_id != request.user.id
            and not can_manage(comment.post.community, request.user)
        ):
            raise PermissionDenied("You cannot delete this comment.")
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostReactionView(APIView):
    permission_classes = [IsAuthenticated, IsEmailVerified]

    def post(self, request, pk):
        post = get_visible_post(request, pk)
        reaction_type = request.data.get("type")
        if reaction_type not in Reaction.Type.values:
            raise ValidationError(
                {"type": f"Choose one of: {', '.join(Reaction.Type.values)}."}
            )

        reaction = post.reactions.filter(user=request.user).first()
        if reaction is None:
            Reaction.objects.create(
                post=post,
                user=request.user,
                type=reaction_type,
            )
            action = "added"
        elif reaction.type == reaction_type:
            reaction.delete()
            action = "removed"
        else:
            reaction.type = reaction_type
            reaction.save(update_fields=["type", "updated_at"])
            action = "updated"

        current = Reaction.objects.filter(post=post, user=request.user).first()
        return Response(
            {
                "action": action,
                "my_reaction": current.type if current else None,
                "reaction_summary": reaction_summary(post),
                "reaction_count": post.reactions.count(),
            }
        )
