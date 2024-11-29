import logging
from datetime import date, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.reports.models import AccountValue, Report
from apps.reports.serializers import (
    ReportDetailsSerializer,
    ReportGenerationSerializer,
    ReportSerializer,
)
from apps.reports.service import XeroApiError, XeroReportService
from apps.xero_api.service import AsyncXeroAuthService, TokenRefreshError

logger = logging.getLogger(__name__)


class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing financial reports.

    Provides CRUD operations for reports and additional actions for
    generating reports and fetching detailed views.
    """

    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Filter reports to show only those belonging to the current user."""
        return Report.objects.filter(user=self.request.user).order_by("-created_at")

    def retrieve(self, request, pk=None):
        report = self.get_object()
        serializer = self.get_serializer(report)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def details(self, request, pk=None):
        report = self.get_object()
        account_values = AccountValue.objects.filter(
            report=report,
            report__user=request.user,
        ).all()

        serializer = ReportDetailsSerializer(
            report, context={"account_balances": account_values}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def generate(self, request: Any) -> Response:
        """
        Generate a new financial report based on provided parameters.

        Returns:
            Response with generated report data or error details
        """
        serializer = ReportGenerationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.validated_data["period"] = self._last_day_of_month(
            serializer.validated_data["period"]
        )

        try:
            tenant = self._validate_and_get_tenant(
                request.user, serializer.validated_data["tenant_name"]
            )
            service = XeroReportService(request)
            report_data = service.generate_report(
                tenant_id=tenant.tenant_id,
                to_date=serializer.validated_data["period"],
                account_type=serializer.validated_data["account_type"],
            )

            report = self._create_report_from_data(
                request.user, serializer.validated_data, report_data
            )
            return Response(
                ReportSerializer(report).data, status=status.HTTP_201_CREATED
            )

        except TokenRefreshError as e:
            logger.warning("Token refresh failed, reauthorization required")
            return Response(
                {
                    "error": "Token refresh failed",
                    "authorization_url": e.authorization_url,
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except (ValidationError, ValueError, XeroApiError) as e:
            logger.warning(f"Report generation failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error in report generation: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate_and_get_tenant(self, user, tenant_name: str = None):
        xero_service = AsyncXeroAuthService()

        tenant = xero_service.get_tenant(user.id, tenant_name=tenant_name)
        if not tenant:
            raise ValueError("No Xero tenants found")
        return tenant

    def _create_report_from_data(self, user, validated_data, report_data):
        logger.info(
            "Creating report from generated data... \nPeriod: %s",
            validated_data["period"],
        )
        report = Report.objects.create(
            user=user,
            period=validated_data["period"],
            account_type=validated_data["account_type"],
        )

        account_values = [
            AccountValue(
                report=report,
                xero_account_id=account_id,
                account_name=data["name"],
                account_balance=data["balance"],
            )
            for account_id, data in report_data.items()
        ]
        AccountValue.objects.bulk_create(account_values)

        return report

    def _last_day_of_month(self, period: date) -> date:
        next_month = (period.month % 12) + 1
        year_adjust = period.year + (1 if period.month == 12 else 0)
        return date(year_adjust, next_month, 1) - timedelta(days=1)
