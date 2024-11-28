from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("xero/", include(("apps.xero_api.urls", "xero_api"), namespace="xero_api")),
    path("reports/", include(("apps.reports.urls", "reports"), namespace="reports")),
]
