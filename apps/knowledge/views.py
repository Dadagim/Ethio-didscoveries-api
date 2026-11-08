from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KnowledgeEntry, KnowledgeFolder
from .serializers import KnowledgeEntrySerializer, KnowledgeFolderSerializer


class KnowledgeFolderListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = KnowledgeFolderSerializer

    def get_queryset(self):
        return (
            KnowledgeFolder.objects.filter(owner=self.request.user)
            .annotate(entry_count=Count("entries"))
            .order_by("name")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class KnowledgeFolderDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = KnowledgeFolderSerializer

    def get_queryset(self):
        return KnowledgeFolder.objects.filter(owner=self.request.user).annotate(
            entry_count=Count("entries")
        )

    def destroy(self, request, *args, **kwargs):
        folder = self.get_object()
        count = folder.entries.count()
        if count:
            return Response(
                {
                    "detail": (
                        "Move or delete the entries in this folder before deleting it."
                    ),
                    "entry_count": count,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        folder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class KnowledgeEntryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = KnowledgeEntry.objects.filter(owner=request.user).select_related(
            "folder"
        )

        folder_id = request.query_params.get("folder", "").strip()
        if folder_id:
            entries = entries.filter(folder_id=folder_id)

        search = request.query_params.get("search", "").strip()
        if search:
            entries = entries.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        return Response(
            {
                "count": entries.count(),
                "results": KnowledgeEntrySerializer(
                    entries, many=True, context={"request": request}
                ).data,
            }
        )

    def post(self, request):
        serializer = KnowledgeEntrySerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(owner=request.user)
        return Response(
            KnowledgeEntrySerializer(entry, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class KnowledgeEntryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(KnowledgeEntry, pk=pk, owner=request.user)

    def get(self, request, pk):
        entry = self.get_object(request, pk)
        return Response(
            KnowledgeEntrySerializer(entry, context={"request": request}).data
        )

    def patch(self, request, pk):
        entry = self.get_object(request, pk)
        serializer = KnowledgeEntrySerializer(
            entry,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(
            KnowledgeEntrySerializer(entry, context={"request": request}).data
        )

    def delete(self, request, pk):
        entry = self.get_object(request, pk)
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
