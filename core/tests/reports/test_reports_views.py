from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.reports.service import XeroReportService

pytestmark = pytest.mark.asyncio


class TestXeroReportService:
    @pytest.fixture
    def xero_service(self):
        request = MagicMock()
        request.user = MagicMock(username="test_user")
        return XeroReportService(request)

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
                                            "Value": "100",
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
                {
                    "AccountID": "c563b607-fb0e-4d06-9ddb-76fdeef20ae3",
                    "Name": "Test Account",
                },
            ]
        }

    @patch("httpx.AsyncClient")
    async def test_get_trial_balance(
        self, mock_client, xero_service, mock_trial_balance_response
    ):
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_trial_balance_response
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        async with httpx.AsyncClient() as client:
            result = await xero_service._get_trial_balance(
                client,
                "tenant-123",
                date(2023, 1, 1),
                {"access_token": "test-token"},
            )

        assert result["c563b607-fb0e-4d06-9ddb-76fdeef20ae3"] == 100.0

    @patch("httpx.AsyncClient")
    async def test_get_accounts(
        self, mock_client, xero_service, mock_accounts_response
    ):
        mock_client_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_accounts_response
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        async with httpx.AsyncClient() as client:
            result = await xero_service._get_accounts(
                client,
                "tenant-123",
                "ASSET",
                {"access_token": "test-token"},
            )

        assert len(result["Accounts"]) == 1
        assert (
            result["Accounts"][0]["AccountID"] == "c563b607-fb0e-4d06-9ddb-76fdeef20ae3"
        )
        assert result["Accounts"][0]["Name"] == "Test Account"
