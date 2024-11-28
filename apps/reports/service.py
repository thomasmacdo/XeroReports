from datetime import date, timedelta
from typing import Dict, Any
import asyncio
import logging
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

    def generate_report(self, tenant_id: str, period: date, account_type: str) -> Dict:
        """
        Generate a new report based on the provided parameters.
        This is the synchronous interface for external use.
        """
        try:
            logger.info(f"Generating report for tenant {tenant_id}...")
            return self._generate_report(tenant_id, period, account_type)
        except TokenExpiredError:
            logger.info("Access token expired, refreshing token...")
            self.xero_service.refresh_token(self.user)
            try:
                return self._generate_report(tenant_id, period, account_type)
            except Exception as e:
                logger.error(f"Error generating report after token refresh: {e}")
                raise ValueError("Error generating report after token refresh")
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise ValueError("Error generating report")

    def _generate_report(self, tenant_id: str, period: date, account_type: str) -> Dict:
        """Generate report using parallel API requests"""
        next_month = (period.month % 12) + 1
        year_adjust = period.year + (1 if period.month == 12 else 0)
        to_date = date(year_adjust, next_month, 1) - timedelta(days=1)

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
            raise  # Propagate the token expired error for handling

        # Create report structure
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
        token: Dict[str, Any],
    ) -> Dict[str, float]:
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
            for row in rows[1:]:
                if row["RowType"] == "Section":
                    continue

                cells = row["Rows"][0]["Cells"]
                account_id = cells[0]["Attributes"][0]["Value"]
                debit_value = float(cells[3].get("Value") or 0)
                credit_value = float(cells[4].get("Value") or 0)
                trial_balances[account_id] = debit_value - credit_value

            return trial_balances

        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise ValueError(f"Failed to fetch trial balance: {e}")

    async def _get_accounts(
        self,
        client: httpx.AsyncClient,
        tenant_id: str,
        account_type: str,
        token: Dict,
    ):
        """Get accounts using async request"""
        try:
            response = await client.get(
                f"https://api.xero.com/api.xro/2.0/Accounts?where=Type%3D%3D%22{account_type}%22",
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

        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise ValueError(f"Failed to fetch accounts: {e}")