import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import XeroAuthState, XeroTenant
from .service import AsyncXeroAuthService

logger = logging.getLogger(__name__)


class XeroConnectView(APIView):
    """Handle initial Xero OAuth2 connection requests.

    Generates and returns the authorization URL that users should be redirected to
    for connecting their Xero account.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.xero_service = AsyncXeroAuthService()

    def get(self, request):
        """Generate a Xero authorization URL.

        Args:
            request: The HTTP request object containing the authenticated user

        Returns:
            Response: JSON containing the authorization URL or error details
        """
        try:
            authorization_url = self.xero_service.generate_authorization_url(
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

    def get(self, request):
        """Process the OAuth2 callback from Xero.

        Args:
            request: The HTTP request object containing 'code' and 'state' params

        Returns:
            Response: JSON indicating success or error of the connection process

        Raises:
            XeroAuthState.DoesNotExist: If the state parameter is invalid
        """
        code = request.query_params.get("code")
        received_state = request.query_params.get("state")

        if not code or not received_state:
            return Response(
                {"error": "Missing code or state parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            auth_state = XeroAuthState.objects.get(state=received_state)
            user = auth_state.user
            auth_state.delete()

            request.user = user

            token_data = self.xero_service.exchange_code_for_token(code)
            self.xero_service.store_token(user.id, token_data)

            connections = self.xero_service.get_connections(token_data["access_token"])

            if not connections:
                return Response(
                    {"error": "No Xero connections found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            XeroTenant.objects.create(
                tenant_id=connections[0]["tenantId"],
                auth_event_id=connections[0]["authEventId"],
                user=user,
                tenant_type=connections[0]["tenantType"],
                tenant_name=connections[0]["tenantName"],
            )

            return Response(
                {"status": "success", "message": "Successfully connected to Xero"}
            )

        except XeroAuthState.DoesNotExist:
            logger.error(f"Invalid state received: {received_state}")
            return Response(
                {"error": "Invalid state parameter"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in Xero callback: {e}")
            return Response(
                {"error": "Failed to complete Xero authentication"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
