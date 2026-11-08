from django.urls import path

from .views import (
    KnowledgeEntryDetailView,
    KnowledgeEntryListCreateView,
    KnowledgeFolderDetailView,
    KnowledgeFolderListCreateView,
)

urlpatterns = [
    path(
        "knowledge/folders/",
        KnowledgeFolderListCreateView.as_view(),
        name="knowledge-folder-list",
    ),
    path(
        "knowledge/folders/<int:pk>/",
        KnowledgeFolderDetailView.as_view(),
        name="knowledge-folder-detail",
    ),
    path(
        "knowledge/entries/",
        KnowledgeEntryListCreateView.as_view(),
        name="knowledge-entry-list",
    ),
    path(
        "knowledge/entries/<int:pk>/",
        KnowledgeEntryDetailView.as_view(),
        name="knowledge-entry-detail",
    ),
]
