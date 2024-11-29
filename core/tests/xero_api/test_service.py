import logging
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User

from apps.xero_api.models import XeroAuthState, XeroTenant, XeroToken
from apps.xero_api.service import AsyncXeroAuthService
from core.tests.factories import UserFactory, XeroTokenFactory

pytestmark = pytest.mark.django_db

logger = logging.getLogger(__name__)


@pytest.fixture
def xero_service() -> AsyncXeroAuthService:
    return AsyncXeroAuthService()


class TestAsyncXeroAuthService:
    def test_generate_authorization_url(self, xero_service):
        user = UserFactory.create()
        auth_url = xero_service.generate_authorization_url(user)

        assert XeroAuthState.objects.filter(user=user).exists()
        assert "client_id=" in auth_url
        assert "redirect_uri=" in auth_url
        assert "scope=" in auth_url
        assert "state=" in auth_url
        assert "response_type=code" in auth_url

    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self, xero_service, mock_token_response):
        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_token_response

            response = xero_service.exchange_code_for_token("test_code")

            assert response == mock_token_response
            mock_post.assert_called_once()

    def test_store_token(self, xero_service, mock_token_response):
        user = UserFactory.create()
        xero_service.store_token(user.id, mock_token_response)

        stored_token = XeroToken.objects.get(user=user)
        assert stored_token.token == mock_token_response

    def test_get_token(self, xero_service, mock_token_response):
        user = UserFactory.create()
        XeroToken.objects.create(user=user, token=mock_token_response)

        token = xero_service.get_token(user.id)
        assert token == mock_token_response

    def test_get_tenant(self, xero_service):
        user = UserFactory.create()
        tenant = XeroTenant.objects.create(
            user=user,
            tenant_id="test_tenant",
            auth_event_id="test_event",
            tenant_type="ORGANISATION",
            tenant_name="Test Org",
        )

        result = xero_service.get_tenant(user.id)
        assert result == tenant

    def test_get_connections_success(self, xero_service):
        test_connections = [
            {
                "tenantId": "test_tenant",
                "authEventId": "test_event",
                "tenantType": "ORGANISATION",
                "tenantName": "Test Org",
            }
        ]

        with patch("httpx.Client.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = test_connections

            connections = xero_service.get_connections("test_token")
            assert connections == test_connections

    def test_get_connections_failure(self, xero_service):
        with patch("httpx.Client.get") as mock_get:
            mock_get.return_value.status_code = 400
            mock_get.return_value.text = "Error"

            connections = xero_service.get_connections("test_token")
            assert connections == []

    @pytest.mark.django_db
    @pytest.mark.asyncio
    def test_refresh_token(
        self,
        xero_service,
        authenticated_user,
    ):
        token = XeroTokenFactory.create(user=authenticated_user)
        assert User.objects.filter(id=authenticated_user.id).exists()
        assert XeroToken.objects.filter(user=authenticated_user).first() == token

        mock_response = {
            "access_token": "new_access_token",
        }

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            refreshed_token = xero_service.refresh_token(authenticated_user.id)

            assert refreshed_token == mock_response
            mock_post.assert_called_once()
