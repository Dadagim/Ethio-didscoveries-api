from django.urls import path

from .views import CommentDetailView, PostCommentsView, PostReactionView

urlpatterns = [
    path(
        "posts/<int:pk>/comments/",
        PostCommentsView.as_view(),
        name="post-comments",
    ),
    path(
        "comments/<int:pk>/",
        CommentDetailView.as_view(),
        name="comment-detail",
    ),
    path(
        "posts/<int:pk>/react/",
        PostReactionView.as_view(),
        name="post-react",
    ),
]
