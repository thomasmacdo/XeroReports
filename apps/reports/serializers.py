from rest_framework import serializers
from datetime import datetime
from xero_python.accounting import AccountType
from apps.reports.models import Report, AccountValue
import logging

logger = logging.getLogger(__name__)


def validate_period_format(value):
    try:
        formats = ["%b-%Y", "%B-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError
    except ValueError:
        raise serializers.ValidationError(
            "Period must be in the format 'Jan-YYYY' or 'January-YYYY'"
        )


class AccountValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountValue
        fields = [
            "account_name",
            "xero_account_id",
            "account_balance",
        ]


class ReportGenerationSerializer(serializers.Serializer):
    tenant_name = serializers.CharField()
    period = serializers.DateField(
        input_formats=["%b-%Y", "%B-%Y"],
        format="%Y-%m-%d",
    )
    account_type = serializers.ChoiceField(
        choices=[(t.value, t.value) for t in AccountType]
    )

    def validate_period(self, value):
        """
        Ensure that the day is always set to 1 for the period field.
        """
        value = value.replace(day=1)
        return value


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "user", "period", "account_type", "created_at"]
        read_only_fields = ["user", "created_at"]


class ReportDetailsSerializer(serializers.ModelSerializer):
    account_balances = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "user",
            "period",
            "account_type",
            "created_at",
            "account_balances",
        ]
        read_only_fields = ["user", "created_at"]

    def get_account_balances(self, obj):
        account_balances = self.context.get("account_balances", [])
        return AccountValueSerializer(account_balances, many=True).data
