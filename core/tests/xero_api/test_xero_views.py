from unittest.mock import AsyncMock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.xero_api.models import XeroAuthState, XeroTenant
from apps.xero_api.service import AsyncXeroAuthService
from apps.xero_api.views import XeroCallbackView, XeroConnectView
from core.tests.factories import UserFactory, XeroAuthStateFactory, XeroTenantFactory

pytestmark = [pytest.mark.django_db, pytest.mark.asyncio]


class TestXeroConnectView:
    @pytest.mark.asyncio
    async def test_xero_connect_view_direct_call(self, authenticated_user):
        factory = APIRequestFactory()
        request = factory.get("/api/xero/connect/")

        force_authenticate(request, user=await authenticated_user)
        with patch.object(
            AsyncXeroAuthService, "generate_authorization_url", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = "https://test.xero.com/auth"

            view_callable = XeroConnectView.as_view()
            response = await view_callable(request)
            response.render()

            assert response.status_code == status.HTTP_200_OK
            assert response.data["authorization_url"] == "https://test.xero.com/auth"
            mock_service.assert_awaited_once()

    @patch("apps.xero_api.views.XeroConnectView.authentication_classes", [])
    @patch("apps.xero_api.views.XeroConnectView.permission_classes", [])
    async def test_error_handling(self, authenticated_user):
        factory = APIRequestFactory()
        request = factory.get("/api/xero/connect/")
        request.user = authenticated_user

        with patch.object(
            AsyncXeroAuthService, "generate_authorization_url", new_callable=AsyncMock
        ) as mock_service:
            mock_service.side_effect = Exception("Test error")

            view_callable = XeroConnectView.as_view()
            response = await view_callable(request)
            response.render()

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.data["error"] == "Test error"

    async def test_unauthenticated_access(self, authenticated_user):
        factory = APIRequestFactory()
        request = factory.get("/api/xero/connect/")
        request.user = authenticated_user

        with patch.object(
            AsyncXeroAuthService, "generate_authorization_url", new_callable=AsyncMock
        ) as mock_service:
            mock_service.return_value = "https://test.xero.com/auth"

            view_callable = XeroConnectView.as_view()
            response = await view_callable(request)
            response.render()

            assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestXeroCallbackView:
    async def test_successful_callback(self):
        user = await UserFactory.acreate()
        auth_state = await XeroAuthStateFactory.acreate(user=user)

        mock_token_data = {
            "access_token": "test_token",
            "refresh_token": "refresh_token",
        }

        mock_connections = [
            {
                "tenantId": "test123",
                "authEventId": "event123",
                "tenantType": "ORGANISATION",
                "tenantName": "Test Company",
            }
        ]

        factory = APIRequestFactory()
        request = factory.get(
            "/api/xero/callback/", data={"code": "test_code", "state": auth_state.state}
        )

        with patch.multiple(
            "apps.xero_api.service.AsyncXeroAuthService",
            exchange_code_for_token=AsyncMock(return_value=mock_token_data),
            get_connections=AsyncMock(return_value=mock_connections),
            store_token=AsyncMock(),
        ):
            view_callable = XeroCallbackView.as_view()
            response = await view_callable(request)
            response.render()

            assert response.status_code == status.HTTP_200_OK
            assert response.data["status"] == "success"

            # Auth state should be deleted after success
            assert not await XeroAuthState.objects.filter(id=auth_state.id).aexists()

    async def test_successful_callback_with_pre_existing_tenants(self):
        user = await UserFactory.acreate()
        auth_state = await XeroAuthStateFactory.acreate(user=user)

        mock_token_data = {
            "access_token": "test_token",
            "refresh_token": "refresh_token",
        }

        await XeroTenantFactory.acreate(user=user, tenant_id="test123")

        mock_connections = [
            {
                "tenantId": "test123",
                "authEventId": "event123",
                "tenantType": "ORGANISATION",
                "tenantName": "Test Company",
            }
        ]

        factory = APIRequestFactory()
        request = factory.get(
            "/api/xero/callback/", data={"code": "test_code", "state": auth_state.state}
        )

        with patch.multiple(
            "apps.xero_api.service.AsyncXeroAuthService",
            exchange_code_for_token=AsyncMock(return_value=mock_token_data),
            get_connections=AsyncMock(return_value=mock_connections),
            store_token=AsyncMock(),
        ):
            view_callable = XeroCallbackView.as_view()
            response = await view_callable(request)
            response.render()

            assert response.status_code == status.HTTP_200_OK
            assert response.data["status"] == "success"

            # ensure that the tenant is not duplicated
            tenant_count = await XeroTenant.objects.filter(user=user).acount()
            assert tenant_count == 1

            tenant = await XeroTenant.objects.filter(user=user).afirst()
            assert tenant.tenant_id == "test123"
            assert tenant.tenant_name == "Test Company"

    async def test_invalid_state(self):
        user = await UserFactory.acreate()
        await XeroAuthStateFactory.acreate(user=user)

        factory = APIRequestFactory()
        request = factory.get(
            "/api/xero/callback/", data={"code": "test_code", "state": "invalid_state"}
        )

        view_callable = XeroCallbackView.as_view()
        response = await view_callable(request)
        response.render()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    async def test_missing_parameters(self):
        factory = APIRequestFactory()
        request = factory.get("/api/xero/callback/")

        view_callable = XeroCallbackView.as_view()
        response = await view_callable(request)
        response.render()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    async def test_exchange_error(self):
        user = await UserFactory.acreate()
        auth_state = await XeroAuthStateFactory.acreate(user=user)

        factory = APIRequestFactory()
        request = factory.get(
            "/api/xero/callback/", data={"code": "test_code", "state": auth_state.state}
        )

        with patch(
            "apps.xero_api.service.AsyncXeroAuthService",
            exchange_code_for_token=AsyncMock(side_effect=Exception("Exchange error")),
        ):
            view_callable = XeroCallbackView.as_view()
            response = await view_callable(request)
            response.render()

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "error" in response.data
