import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from adrf.views import APIView
from apps.xero_api.models import XeroAuthState, XeroTenant
from apps.xero_api.service import AsyncXeroAuthService
from core.authentication import AsyncJWTAuthentication

logger = logging.getLogger(__name__)


class XeroConnectView(APIView):
    """Handle initial Xero OAuth2 connection requests.

    Generates and returns the authorization URL that users should be redirected to
    for connecting their Xero account.
    """

    authentication_classes = [AsyncJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.xero_service = AsyncXeroAuthService()

    async def get(self, request):
        """Generate a Xero authorization URL.

        Args:
            request: The HTTP request object containing the authenticated user

        Returns:
            Response: JSON containing the authorization URL or error details
        """
        try:
            authorization_url = await self.xero_service.generate_authorization_url(
                request.user
            )
            return Response({"authorization_url": authorization_url})
        except Exception as e:
            logger.error(f"Error in Xero connect: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class XeroCallbackView(APIView):
    """Handle OAuth2 callbacks from Xero.

    Processes the authorization code from Xero, exchanges it for tokens,
    and stores the connection information.
    """

    authentication_classes = []
    permission_classes = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.xero_service = AsyncXeroAuthService()

    async def get(self, request):
        """Process the OAuth2 callback from Xero.
        Making sure that the state is valid and hasn't been tampered with.

        Args:
            request: The HTTP request object containing 'code' and 'state' params

        Returns:
            Response: JSON indicating success or error
        """
        code = request.query_params.get("code")
        received_state = request.query_params.get("state")

        if not code or not received_state:
            logger.warning("Missing code or state parameter in request")
            return Response(
                {"error": "Missing code or state parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            auth_state = await XeroAuthState.objects.select_related("user").aget(
                state=received_state
            )
        except XeroAuthState.DoesNotExist:
            logger.error(f"Invalid state parameter: {received_state}")
            return Response(
                {"error": "Invalid state parameter"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = auth_state.user
        logger.debug(f"Found auth state for user_id: {user.id}")

        request.user = user

        try:
            token_data = await self.xero_service.exchange_code_for_token(code)
        except Exception:
            logger.exception("Error exchanging code for token")
            return Response(
                {"error": "Failed to exchange code for token"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        await auth_state.adelete()
        logger.debug("Auth state deleted after successful token exchange")

        try:
            await self.xero_service.store_token(user.id, token_data)
        except Exception:
            logger.exception(f"Error storing token for user {user.id}")
            return Response(
                {"error": "Failed to store Xero token"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            connections = await self.xero_service.get_connections(
                token_data["access_token"]
            )
        except Exception:
            logger.exception(f"Error fetching connections for user {user.id}")
            return Response(
                {"error": "Failed to retrieve Xero connections"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not connections:
            logger.warning(f"No Xero connections found for user {user.id}")
            return Response(
                {"error": "No Xero connections found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        tenant_defaults = []
        for connection in connections:
            tenant_defaults.append(
                {
                    "tenant_id": connection["tenantId"],
                    "auth_event_id": connection["authEventId"],
                    "user": user,
                    "tenant_type": connection["tenantType"],
                    "tenant_name": connection["tenantName"],
                }
            )

        try:
            tenants_to_create = [XeroTenant(**defaults) for defaults in tenant_defaults]

            await XeroTenant.objects.abulk_create(
                tenants_to_create,
                update_conflicts=True,
                unique_fields=["tenant_id", "user"],
                update_fields=["auth_event_id", "tenant_type", "tenant_name"],
            )

        except Exception as e:
            logger.exception(f"Error storing Xero tenants for user {user.id}: {str(e)}")
            return Response(
                {"error": "Failed to store Xero tenant information"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"status": "success", "message": "Successfully connected to Xero"},
            status=status.HTTP_200_OK,
        )
