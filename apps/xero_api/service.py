import base64
import logging
import secrets
from typing import Any

import httpx
from django.conf import settings
from django.contrib.auth.models import User

from .models import XeroAuthState, XeroTenant, XeroToken

logger = logging.getLogger(__name__)


class TokenRefreshError(Exception):
    """Raised when token refresh fails and reauthorization is needed."""

    def __init__(self, authorization_url):
        self.authorization_url = authorization_url
        super().__init__("Token refresh failed, reauthorization required")


class AsyncXeroAuthService:
    """Manages Xero OAuth2 authentication flow and token operations.

    Handles authorization URL generation, token exchange, storage,
    and refresh operations.
    """

    def __init__(self):
        self.config = settings.XERO_API_CONFIG
        self.client_id = settings.XERO_CLIENT_ID
        self.client_secret = settings.XERO_SECRET_KEY
        self.scope = settings.XERO_SCOPES
        self.redirect_uri = settings.XERO_REDIRECT_URI
        self.token_url = self.config["TOKEN_URL"]
        self.connections = self.config["CONNECTIONS_URL"]
        self.authorize_url = self.config["AUTHORIZE_URL"]

    async def generate_authorization_url(self, user: User) -> str:
        """Generate a Xero OAuth2 authorization URL.

        Args:
            user: The user initiating the connection

        Returns:
            str: The authorization URL including state parameter

        """
        logger.info(f"Generating authorization URL for user {user.username}")
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scope),
            "response_type": "code",
            "state": await self._generate_state(user),
        }
        return f"{self.authorize_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    async def _generate_state(self, user: User) -> str:
        state = secrets.token_urlsafe(32)
        await XeroAuthState.objects.acreate(user=user, state=state)
        return state

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for token."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient() as client:
            logger.debug("Exchanging code for token")
            response = await client.post(
                self.token_url,
                headers={
                    "Authorization": f"Basic {encoded_credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise Exception(f"Failed to exchange code for token: {response.text}")

            return response.json()

    async def get_token(self, user_id: int) -> dict[str, Any] | None:
        token = await XeroToken.objects.filter(user_id=user_id).afirst()
        return token.token if token else None

    async def refresh_token(self, user_id: int) -> dict[str, Any]:
        token_data = await self.get_token(user_id=user_id)
        if not token_data:
            raise Exception("No token found")

        try:
            refresh_token = token_data["refresh_token"]
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config["TOKEN_URL"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    auth=(self.client_id, self.client_secret),
                )

                if response.status_code != 200:
                    logger.error(f"Token refresh failed: {response.text}")
                    user = await User.objects.aget(id=user_id)
                    auth_url = await self.generate_authorization_url(user)
                    raise TokenRefreshError(auth_url)

                new_token_data = response.json()
                await self.store_token(user_id, new_token_data)
                return new_token_data

        except httpx.RequestError as e:
            logger.error(f"Token refresh request failed: {e}")
            user = await User.objects.aget(id=user_id)
            auth_url = await self.generate_authorization_url(user)
            raise TokenRefreshError(auth_url)

    async def store_token(self, user_id: int, token_data: dict[str, Any]) -> None:
        await XeroToken.objects.aupdate_or_create(
            user_id=user_id, defaults={"token": token_data}
        )

    async def get_tenant(self, user_id: int, tenant_name: str) -> XeroTenant | None:
        """Retrieve Xero tenant for the current user."""
        logger.info(f"Fetching tenants for user {user_id}")
        try:
            return await XeroTenant.objects.filter(
                user_id=user_id, tenant_name=tenant_name
            ).afirst()
        except Exception as e:
            logger.error(f"Error fetching tenants for user {user_id}: {str(e)}")
            return None

    async def get_connections(self, access_token: str) -> list:
        """Synchronous version for getting connections."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.connections,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 200:
                    return response.json()

                logger.error(f"Failed to get Xero connections: {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error getting Xero connections: {str(e)}")
            return []
