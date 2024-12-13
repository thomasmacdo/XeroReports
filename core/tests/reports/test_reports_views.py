from unittest.mock import AsyncMock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.reports.service import XeroReportService
from apps.reports.views import ReportViewSet
from apps.xero_api.service import TokenRefreshError
from core.tests.factories import AccountValueFactory, ReportFactory, XeroTenantFactory

pytestmark = [pytest.mark.django_db, pytest.mark.asyncio]

factory = APIRequestFactory()


class TestReportViewSet:
    @pytest.fixture
    def mock_report_data(self):
        return {
            "acc-123": {"name": "Test Account", "balance": 100.00},
        }

    async def test_list_reports(self, authenticated_user):
        auth_user = await authenticated_user
        for _ in range(3):
            await ReportFactory.acreate(user=auth_user)

        request = factory.get("/api/reports/")
        request.user = auth_user

        force_authenticate(request, user=auth_user)
        view = ReportViewSet.as_view({"get": "list"})
        response = await view(request)
        response.render()

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    async def test_report_details(self, authenticated_user):
        auth_user = await authenticated_user
        report = await ReportFactory.acreate(user=auth_user)
        await AccountValueFactory.acreate(report=report)

        factory = APIRequestFactory()
        request = factory.get(f"/api/reports/{report.id}/details/")
        request.user = auth_user

        force_authenticate(request, user=auth_user)

        view = ReportViewSet.as_view({"get": "details"})
        response = await view(request, pk=report.id)

        assert response.status_code == status.HTTP_200_OK
        assert "account_balances" in response.data

    async def test_generate_report_success(self, authenticated_user, mock_report_data):
        auth_user = await authenticated_user
        tenant = await XeroTenantFactory.acreate(user=auth_user)

        factory = APIRequestFactory()
        request_data = {
            "tenant_name": tenant.tenant_name,
            "period": "Jan-2023",
            "account_type": "CURRENT",
        }
        request = factory.post(
            "/api/reports/generate/", data=request_data, format="json"
        )
        request.user = auth_user

        force_authenticate(request, user=auth_user)

        with patch.object(
            XeroReportService, "generate_report", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = mock_report_data

            view = ReportViewSet.as_view({"post": "generate"})
            response = await view(request)
            response.render()

            assert response.status_code == status.HTTP_201_CREATED
            assert "id" in response.data

    async def test_generate_report_token_error(self, authenticated_user):
        auth_user = await authenticated_user
        tenant = await XeroTenantFactory.acreate(user=auth_user)

        factory = APIRequestFactory()
        request_data = {
            "tenant_name": tenant.tenant_name,
            "period": "Jan-2023",
            "account_type": "CURRENT",
        }
        request = factory.post(
            "/api/reports/generate/", data=request_data, format="json"
        )
        request.user = auth_user

        force_authenticate(request, user=auth_user)

        with patch.object(
            XeroReportService, "generate_report", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.side_effect = TokenRefreshError("http://auth.url")

            view = ReportViewSet.as_view({"post": "generate"})
            response = await view(request)
            response.render()

            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "authorization_url" in response.data

    @patch("apps.reports.views.ReportViewSet.permission_classes", [])
    async def test_generate_report_validation_error(self, authenticated_user):
        factory = APIRequestFactory()
        request_data = {
            "period": "invalid-date",
            "account_type": "ASSET",
        }
        request = factory.post(
            "/api/reports/generate/", data=request_data, format="json"
        )
        request.user = authenticated_user

        view = ReportViewSet.as_view({"post": "generate"})
        response = await view(request)
        response.render()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
