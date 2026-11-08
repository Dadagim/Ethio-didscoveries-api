from django.urls import path

from .views import (
    CommunityDetailView,
    CommunityJoinView,
    CommunityLeaveView,
    CommunityListCreateView,
    CommunityMembershipModerationView,
    CommunityMembersView,
)

urlpatterns = [
    path("communities/", CommunityListCreateView.as_view(), name="community-list"),
    path(
        "communities/<slug:slug>/",
        CommunityDetailView.as_view(),
        name="community-detail",
    ),
    path(
        "communities/<slug:slug>/join/",
        CommunityJoinView.as_view(),
        name="community-join",
    ),
    path(
        "communities/<slug:slug>/leave/",
        CommunityLeaveView.as_view(),
        name="community-leave",
    ),
    path(
        "communities/<slug:slug>/members/",
        CommunityMembersView.as_view(),
        name="community-members",
    ),
    path(
        "communities/<slug:slug>/members/<int:membership_id>/<str:action>/",
        CommunityMembershipModerationView.as_view(),
        name="community-membership-moderate",
    ),
]
