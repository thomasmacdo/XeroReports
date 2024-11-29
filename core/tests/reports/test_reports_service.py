import logging
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.reports.service import TokenExpiredError, XeroReportService
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
                                    "RowType": "Row",
                                    "Cells": [
                                        {
                                            "Value": "Sales (200)",
                                            "Attributes": [{"Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3", "Id": "account"}]
                                        },
                                        {
                                            "Value": "",
                                            "Attributes": [{"Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3", "Id": "account"}]
                                        },
                                        {
                                            "Value": "",
                                            "Attributes": [{"Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3", "Id": "account"}]
                                        },
                                        {
                                            "Value": "16576.04",
                                            "Attributes": [{"Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3", "Id": "account"}]
                                        },
                                        {
                                            "Value": "26630.00",
                                            "Attributes": [{"Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3", "Id": "account"}]
                                        }
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
        return {"Accounts": [{"AccountID": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3", "Name": "Sales"}]}

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

        assert "c563b607-fb0e-4d06-9ddb-76fdeef20ae3" in result
        assert result["c563b607-fb0e-4d06-9ddb-76fdeef20ae3"] == -10053.96

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
        assert result["Accounts"][0]["AccountID"] == "c563b607-fb0e-4d06-9ddb-76fdeef20ae3"

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
            {"c563b607-fb0e-4d06-9ddb-76fdeef20ae3": 16576.04},
        )

        result = service.generate_report("tenant-123", date(2023, 1, 1), "ASSET")

        assert "c563b607-fb0e-4d06-9ddb-76fdeef20ae3" in result
        assert result["c563b607-fb0e-4d06-9ddb-76fdeef20ae3"]["name"] == "Sales"
        assert result["c563b607-fb0e-4d06-9ddb-76fdeef20ae3"]["balance"] == 16576.04

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
