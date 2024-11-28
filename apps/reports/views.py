from typing import Any
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ValidationError

from apps.xero_api.service import AsyncXeroAuthService

from apps.reports.serializers import (
    ReportDetailsSerializer,
    ReportGenerationSerializer,
    ReportSerializer,
)
from apps.reports.service import XeroReportService, XeroApiError
from apps.reports.models import AccountValue, Report

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

        try:
            tenant = self._validate_and_get_tenant(request.user)
            service = XeroReportService(request)
            report_data = service.generate_report(
                tenant_id=tenant.tenant_id,
                period=serializer.validated_data["period"],
                account_type=serializer.validated_data["account_type"],
            )

            report = self._create_report_from_data(
                request.user, serializer.validated_data, report_data
            )
            return Response(
                ReportSerializer(report).data, status=status.HTTP_201_CREATED
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

    def _validate_and_get_tenant(self, user):
        xero_service = AsyncXeroAuthService()

        tenant = xero_service.get_tenant(user.id)
        if not tenant:
            raise ValueError("No Xero tenants found")
        return tenant

    def _create_report_from_data(self, user, validated_data, report_data):
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
