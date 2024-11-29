import asyncio
import logging
from datetime import date
from typing import Any

import httpx
from asgiref.sync import async_to_sync

from apps.xero_api.service import AsyncXeroAuthService

logger = logging.getLogger(__name__)


class XeroApiError(Exception):
    """Base exception for Xero API related errors."""

    pass


class TokenExpiredError(XeroApiError):
    """Raised when the Xero API token has expired."""

    pass


class XeroReportService:
    """Service for generating financial reports from Xero API data."""

    def __init__(self, request: Any) -> None:
        self.xero_service = AsyncXeroAuthService()
        self.user = request.user

    def generate_report(self, tenant_id: str, to_date: date, account_type: str) -> dict:
        """
        Generate a new report based on the provided parameters.
        This is the synchronous interface for external use.
        """
        try:
            return self._generate_report(tenant_id, to_date, account_type)
        except TokenExpiredError:
            logger.info("Access token expired, refreshing token...")
            self.xero_service.refresh_token(self.user)
            try:
                return self._generate_report(tenant_id, to_date, account_type)
            except Exception as e:
                logger.error(f"Error generating report after token refresh: {e}")
                raise ValueError("Error generating report after token refresh")
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise ValueError("Error generating report")

    def _generate_report(
        self, tenant_id: str, to_date: date, account_type: str
    ) -> dict:
        """Generate report using parallel API requests"""
        token = self.xero_service.get_token(self.user)

        async def fetch_data():
            async with httpx.AsyncClient() as client:
                accounts_task = self._get_accounts(
                    client, tenant_id, account_type, token
                )
                trial_balance_task = self._get_trial_balance(
                    client, tenant_id, to_date, token
                )
                return await asyncio.gather(accounts_task, trial_balance_task)

        # Run async tasks
        try:
            accounts_data, trial_balance_data = async_to_sync(fetch_data)()
        except TokenExpiredError:
            raise

        report = {}
        for account in accounts_data.get("Accounts", []):
            report[account["AccountID"]] = {
                "name": account["Name"],
                "balance": trial_balance_data.get(account["AccountID"], 0),
            }

        return report

    async def _get_trial_balance(
        self,
        client: httpx.AsyncClient,
        tenant_id: str,
        date: date,
        token: dict[str, Any],
    ) -> dict[str, float]:
        """
        Fetch trial balance data from Xero API.

        Args:
            client: HTTP client for making requests
            tenant_id: Xero tenant identifier
            date: Date for trial balance
            token: Authentication token

        Returns:
            Dict mapping account IDs to their balances

        Raises:
            TokenExpiredError: If the API token has expired
            ValueError: If the API request fails
        """
        logger.info(f"Getting trial balance for tenant {tenant_id}...")
        try:
            response = await client.get(
                f"https://api.xero.com/api.xro/2.0/Reports/TrialBalance?date={date}",
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                    "Xero-tenant-id": tenant_id,
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()

            if response.status_code == 401:
                raise TokenExpiredError(
                    "Access token expired while fetching trial balance."
                )

            data = response.json()
            trial_balances = {}

            rows = data["Reports"][0]["Rows"]

            ytd_debit_value_index, ytd_credit_value_index = 3, 4

            # Skip the first row (header)
            for row in rows[1:]:
                rowType = row["Rows"][0]["RowType"]
                if rowType == "SummaryRow":
                    continue

                cells = row["Rows"][0]["Cells"]
                account_id = cells[0]["Attributes"][0]["Value"]

                debit_value = float(cells[ytd_debit_value_index].get("Value") or 0)
                credit_value = float(cells[ytd_credit_value_index].get("Value") or 0)
                trial_balances[account_id] = debit_value - credit_value

            return trial_balances

        except httpx.HTTPError:
            if response.status_code == 401:
                raise TokenExpiredError(
                    "Access token expired while fetching trial balance."
                )
            raise ValueError("Error fetching trial balance from Xero API")

    async def _get_accounts(
        self,
        client: httpx.AsyncClient,
        tenant_id: str,
        account_type: str,
        token: dict,
    ):
        """Get accounts using async request"""
        try:
            response = await client.get(
                f"https://api.xero.com/api.xro/2.0/Accounts?where=Type%3D%3D%22{account_type}%22",  # noqa
                headers={
                    "Authorization": f"Bearer {token['access_token']}",
                    "Xero-tenant-id": tenant_id,
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()

            if response.status_code == 401:
                raise TokenExpiredError("Access token expired while fetching accounts.")

            return response.json()

        except httpx.HTTPError:
            if response.status_code == 401:
                raise TokenExpiredError("Access token expired while fetching accounts.")
            raise ValueError("Error fetching accounts from Xero API")
