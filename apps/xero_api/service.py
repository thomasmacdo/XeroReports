import base64
import httpx
from typing import Dict, Any, Optional
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from asgiref.sync import sync_to_async
import requests
from .models import XeroTenant, XeroToken, XeroAuthState
import logging

logger = logging.getLogger(__name__)


class AsyncXeroAuthService:
    """Manages Xero OAuth2 authentication flow and token operations.

    Handles authorization URL generation, token exchange, storage, and refresh operations.
    Supports both synchronous and asynchronous operations where needed.
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

    def generate_authorization_url(self, user: User) -> str:
        """Generate a Xero OAuth2 authorization URL.

        Args:
            user: The user initiating the connection

        Returns:
            str: The authorization URL including state parameter

        Note:
            This is a synchronous operation that creates a state record
            for CSRF protection.
        """
        logger.info(f"Generating authorization URL for user {user.username}")
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scope),
            "response_type": "code",
            "state": self._generate_state_sync(user),
        }
        return f"{self.authorize_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    @sync_to_async
    def _generate_state(self, user: User) -> str:
        import secrets

        state = secrets.token_urlsafe(32)
        with transaction.atomic():
            XeroAuthState.objects.create(user=user, state=state)
        return state

    def _generate_state_sync(self, user: User) -> str:
        import secrets

        state = secrets.token_urlsafe(32)
        with transaction.atomic():
            XeroAuthState.objects.create(user=user, state=state)
        return state

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Synchronous version for token exchange."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        with httpx.Client() as client:
            response = client.post(
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

    def get_token(self, user_id: int) -> Optional[Dict[str, Any]]:
        token = XeroToken.objects.filter(user_id=user_id).first()
        if not token:
            logger.error(f"No token found for user {user_id}")
            return None
        return token.token

    def refresh_token(self, user_id: int) -> Dict[str, Any]:
        token_data = self.get_token(user_id=user_id)
        if not token_data:
            raise Exception("No token found")

        refresh_token = token_data["refresh"]
        response = requests.post(
            self.config["TOKEN_URL"],
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(self.client_id, self.client_secret),
        )

        if response.status_code != 200:
            logger.error(f"Token refresh failed: {response.text}")
            raise Exception(f"Failed to refresh token: {response.text}")

        new_token_data = response.json()
        self.store_token(user_id, new_token_data)
        return new_token_data

    def store_token(self, user_id: int, token_data: Dict[str, Any]) -> None:
        """Synchronous version for token storage."""
        XeroToken.objects.update_or_create(
            user_id=user_id, defaults={"token": token_data}
        )

    def get_tenant(self, user_id: int) -> Optional[list]:
        """Retrieve Xero tenant for the current user."""
        logger.info(f"Fetching tenants for user {user_id}")
        try:
            return XeroTenant.objects.filter(user_id=user_id).first()
        except Exception as e:
            logger.error(f"Error fetching tenants for user {user_id}: {str(e)}")
            return None

    def get_connections(self, access_token: str) -> list:
        """Synchronous version for getting connections."""
        try:
            with httpx.Client() as client:
                response = client.get(
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
