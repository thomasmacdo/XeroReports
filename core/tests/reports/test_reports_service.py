import logging
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.reports.service import XeroReportService
from core.tests.factories import XeroTokenFactory

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.django_db, pytest.mark.asyncio]


class TestXeroReportService:
    @pytest.fixture
    async def service(self, authenticated_user):
        mock_request = MagicMock()
        mock_request.user = await authenticated_user
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
                                            "Attributes": [
                                                {
                                                    "Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3",  # noqa
                                                    "Id": "account",
                                                }
                                            ],
                                        },
                                        {
                                            "Value": "",
                                            "Attributes": [
                                                {
                                                    "Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3",  # noqa
                                                    "Id": "account",
                                                }
                                            ],
                                        },
                                        {
                                            "Value": "",
                                            "Attributes": [
                                                {
                                                    "Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3",  # noqa
                                                    "Id": "account",
                                                }
                                            ],
                                        },
                                        {
                                            "Value": "16576.04",
                                            "Attributes": [
                                                {
                                                    "Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3",  # noqa
                                                    "Id": "account",
                                                }
                                            ],
                                        },
                                        {
                                            "Value": "26630.00",
                                            "Attributes": [
                                                {
                                                    "Value": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3",  # noqa
                                                    "Id": "account",
                                                }
                                            ],
                                        },
                                    ],
                                }
                            ],
                        },
                    ]
                }
            ]
        }

    @pytest.fixture
    def mock_accounts_response(self):
        return {
            "Accounts": [
                {"AccountID": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3", "Name": "Sales"}
            ]
        }

    @pytest.fixture
    def mock_failed_response(self):
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPError("Token expired")
        return mock_response

    async def test_get_trial_balance(self, service, mock_trial_balance_response):
        service = await service

        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_trial_balance_response
        mock_response.raise_for_status = MagicMock()
        mock_client_instance.get.return_value = mock_response

        result = await service._get_trial_balance(
            mock_client_instance,
            "tenant-123",
            date(2023, 1, 1),
            {"access_token": "test-token"},
        )

        assert "c563b607-fb0e-4d06-9ddb-76fdeef20ae3" in result
        assert result["c563b607-fb0e-4d06-9ddb-76fdeef20ae3"] == -10053.96

    async def test_get_accounts(self, service, mock_accounts_response):
        service = await service

        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_accounts_response
        mock_client_instance.get.return_value = mock_response

        result = await service._get_accounts(
            mock_client_instance,
            "tenant-123",
            "ASSET",
            {"access_token": "test-token"},
        )

        assert len(result["Accounts"]) == 1
        assert (
            result["Accounts"][0]["AccountID"] == "c563b607-fb0e-4d06-9ddb-76fdeef20ae3"
        )

    async def test_generate_report(
        self,
        service,
        mock_accounts_response,
        mock_trial_balance_response,
    ):
        service = await service
        mock_token = {"access_token": "test-token"}

        with patch("apps.reports.service.AsyncXeroAuthService") as mock_auth:
            mock_auth_instance = mock_auth.return_value
            mock_auth_instance.get_token = AsyncMock(return_value=mock_token)
            service.xero_service = mock_auth_instance

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()

                tb_response = MagicMock()
                tb_response.status_code = 200
                tb_response.json.return_value = mock_trial_balance_response

                acc_response = MagicMock()
                acc_response.status_code = 200
                acc_response.json.return_value = mock_accounts_response

                mock_client_instance.get.side_effect = [acc_response, tb_response]
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                result = await service.generate_report(
                    "tenant-123", date(2023, 1, 1), "ASSET"
                )

                assert "c563b607-fb0e-4d06-9ddb-76fdeef20ae3" in result
                assert result["c563b607-fb0e-4d06-9ddb-76fdeef20ae3"]["name"] == "Sales"
                assert (
                    result["c563b607-fb0e-4d06-9ddb-76fdeef20ae3"]["balance"]
                    == -10053.96
                )

    async def test_generate_report_token_expired(
        self,
        service,
        mock_failed_response,
    ):
        service = await service
        await XeroTokenFactory.acreate(user=service.user)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_failed_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            with patch("apps.reports.service.AsyncXeroAuthService") as mock_auth:
                mock_auth_instance = mock_auth.return_value
                mock_auth_instance.refresh_token = AsyncMock(
                    side_effect=ValueError("Token expired")
                )
                mock_auth_instance.get_token = AsyncMock(
                    return_value={"access_token": "test-token"}
                )

                service.xero_service = mock_auth_instance

                with pytest.raises(ValueError, match="Token expired"):
                    await service.generate_report(
                        "tenant-123", date(2023, 1, 1), "ASSET"
                    )

                mock_auth_instance.refresh_token.assert_called_once_with(service.user)
