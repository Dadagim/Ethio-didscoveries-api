from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.common.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.communities.urls")),
    path("api/", include("apps.posts.urls")),
    path("api/", include("apps.interactions.urls")),
    path("api/", include("apps.knowledge.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
