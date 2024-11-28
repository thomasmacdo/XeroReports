from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.reports.views import ReportViewSet

router = DefaultRouter()
router.register(r"", ReportViewSet, basename="report")

urlpatterns = [
    path("", include(router.urls)),
]
