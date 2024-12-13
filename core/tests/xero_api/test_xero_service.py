import base64
import logging
from unittest.mock import patch

import httpx
import pytest

from apps.xero_api.models import XeroTenant, XeroToken
from apps.xero_api.service import AsyncXeroAuthService
from core.tests.factories import UserFactory, XeroTokenFactory

pytestmark = [pytest.mark.django_db, pytest.mark.asyncio]

logger = logging.getLogger(__name__)


@pytest.fixture
def xero_service() -> AsyncXeroAuthService:
    return AsyncXeroAuthService()


@pytest.fixture
def mock_token_response():
    return {
        "access_token": "test_access_token",
        "expires_in": 1800,
        "token_type": "Bearer",
        "refresh_token": "test_refresh_token",
        "scope": "openid profile email accounting.transactions",
    }


class TestAsyncXeroAuthService:
    @pytest.fixture
    async def service(self):
        user = await UserFactory.acreate()
        return AsyncXeroAuthService(), user

    async def test_generate_authorization_url(self, service):
        xero_service, user = await service
        auth_url = await xero_service.generate_authorization_url(user)

        assert "client_id=" in auth_url
        assert "redirect_uri=" in auth_url
        assert "scope=" in auth_url
        assert "state=" in auth_url
        assert "response_type=code" in auth_url

    async def test_exchange_code_for_token(
        self,
        xero_service: AsyncXeroAuthService,
        mock_token_response,
    ):
        class MockResponse:
            status_code = 200
            _json = mock_token_response
            text = str(mock_token_response)

            def json(self):
                return self._json

        async def mock_post(*args, **kwargs):
            return MockResponse()

        credentials = f"{xero_service.client_id}:{xero_service.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        with patch("httpx.AsyncClient.post", side_effect=mock_post) as mock:
            response = await xero_service.exchange_code_for_token("test_code")
            assert response == mock_token_response

            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args[0][0] == xero_service.token_url
            assert call_args[1]["headers"] == {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            assert call_args[1]["data"] == {
                "grant_type": "authorization_code",
                "code": "test_code",
                "redirect_uri": xero_service.redirect_uri,
            }

    async def test_store_token(
        self,
        xero_service: AsyncXeroAuthService,
        mock_token_response,
    ):
        user = await UserFactory.acreate()
        await xero_service.store_token(user.id, mock_token_response)

        stored_token = await XeroToken.objects.aget(user=user)
        assert stored_token.token == mock_token_response

    async def test_get_token(
        self, xero_service: AsyncXeroAuthService, mock_token_response
    ):
        user = await UserFactory.acreate()
        await XeroToken.objects.acreate(user=user, token=mock_token_response)

        token = await xero_service.get_token(user.id)
        assert token == mock_token_response

    async def test_get_tenant(self, xero_service: AsyncXeroAuthService):
        user = await UserFactory.acreate()
        create_tenant = XeroTenant.objects.acreate
        tenant = await create_tenant(
            user=user,
            tenant_id="test_tenant",
            auth_event_id="test_event",
            tenant_type="ORGANISATION",
            tenant_name="Test Org",
        )

        result = await xero_service.get_tenant(user.id, "Test Org")
        assert result == tenant

    async def test_get_connections_success(self, xero_service: AsyncXeroAuthService):
        test_connections = [
            {
                "tenantId": "test_tenant",
                "authEventId": "test_event",
                "tenantType": "ORGANISATION",
                "tenantName": "Test Org",
            }
        ]

        class MockResponse:
            status_code = 200
            _json = test_connections

            def json(self):
                return self._json

        async def mock_get(*args, **kwargs):
            return MockResponse()

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            connections = await xero_service.get_connections("test_token")
            assert connections == test_connections

    async def test_get_connections_failure(self, xero_service: AsyncXeroAuthService):
        class MockResponse:
            status_code = 400
            text = "Error"

            async def json(self):
                raise httpx.HTTPError("Bad Request")

        async def mock_get(*args, **kwargs):
            return MockResponse()

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            connections = await xero_service.get_connections("test_token")
            assert connections == []

    async def test_refresh_token(self, xero_service: AsyncXeroAuthService):
        token = await XeroTokenFactory.acreate()
        user = token.user

        new_token = {"access_token": "new_access_token"}

        class MockResponse:
            status_code = 200
            _json = new_token

            def json(self):
                return self._json

        async def mock_post(*args, **kwargs):
            return MockResponse()

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            refreshed_token = await xero_service.refresh_token(user.id)
            assert refreshed_token == new_token
