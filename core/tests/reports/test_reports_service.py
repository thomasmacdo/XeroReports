import httpx
import pytest
from datetime import date
from unittest.mock import patch, MagicMock, AsyncMock
from apps.reports.service import XeroReportService, TokenExpiredError
import logging

from core.tests.factories import XeroTokenFactory

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db


class TestXeroReportService:
    @pytest.fixture
    def service(self, authenticated_user):
        mock_request = MagicMock()
        mock_request.user = authenticated_user
        return XeroReportService(mock_request)

    @pytest.fixture
    def mock_trial_balance_response(self):
        return {
            "Reports": [
                {
                    "Rows": [
                        {"RowType": "Header"},
                        {
                            "RowType": "Row",
                            "Rows": [
                                {
                                    "Cells": [
                                        {"Attributes": [{"Value": "acc-123"}]},
                                        {},
                                        {},
                                        {"Value": "100.00"},
                                        {"Value": "0.00"},
                                    ]
                                }
                            ],
                        },
                    ]
                }
            ]
        }

    @pytest.fixture
    def mock_accounts_response(self):
        return {"Accounts": [{"AccountID": "acc-123", "Name": "Test Account"}]}

    @pytest.fixture
    def mock_failed_response(self):
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPError("Token expired")
        return mock_response

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_get_trial_balance(
        self, mock_client, service, mock_trial_balance_response
    ):
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_response.json.return_value = mock_trial_balance_response
        mock_response.raise_for_status = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        async with httpx.AsyncClient() as client:
            result = await service._get_trial_balance(
                client,
                "tenant-123",
                date(2023, 1, 1),
                {"access_token": "test-token"},
            )

        assert "acc-123" in result
        assert result["acc-123"] == 100.00

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_get_accounts(self, mock_client, service, mock_accounts_response):
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_accounts_response
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        async with httpx.AsyncClient() as client:
            result = await service._get_accounts(
                client,
                "tenant-123",
                "ASSET",
                {"access_token": "test-token"},
            )

        logger.info(result)
        assert len(result["Accounts"]) == 1
        assert result["Accounts"][0]["AccountID"] == "acc-123"

    @patch("apps.reports.service.async_to_sync")
    def test_generate_report(
        self,
        mock_async_to_sync,
        service,
        mock_accounts_response,
        mock_trial_balance_response,
    ):
        mock_async_to_sync.return_value.return_value = (
            mock_accounts_response,
            {"acc-123": 100.00},
        )

        result = service.generate_report("tenant-123", date(2023, 1, 1), "ASSET")

        assert "acc-123" in result
        assert result["acc-123"]["name"] == "Test Account"
        assert result["acc-123"]["balance"] == 100.00

    @patch("apps.reports.service.async_to_sync")
    @patch("apps.reports.service.AsyncXeroAuthService")
    def test_generate_report_token_expired(
        self,
        mock_auth_service,
        mock_async_to_sync,
        service,
        mock_failed_response,
        authenticated_user,
    ):
        XeroTokenFactory.create(user=authenticated_user)

        mock_async_to_sync.return_value.side_effect = TokenExpiredError("Token expired")

        mock_auth_instance = mock_auth_service.return_value
        mock_auth_instance.refresh_token = MagicMock(
            side_effect=ValueError("Token expired")
        )
        mock_auth_instance.get_token = MagicMock(
            return_value={"access_token": "test-token"}
        )

        service.xero_service = mock_auth_instance

        with pytest.raises(ValueError, match="Token expired"):
            service.generate_report("tenant-123", date(2023, 1, 1), "ASSET")

        mock_auth_instance.refresh_token.assert_called_once_with(service.user)