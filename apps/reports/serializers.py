import logging
from datetime import datetime

from asgiref.sync import sync_to_async
from rest_framework import serializers

from adrf.serializers import ModelSerializer, Serializer
from apps.reports.models import AccountValue, Report
from apps.xero_api.account_type import AccountType

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


class AccountValueSerializer(ModelSerializer):
    class Meta:
        model = AccountValue
        fields = [
            "account_name",
            "xero_account_id",
            "account_balance",
        ]


class ReportGenerationSerializer(Serializer):
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


class ReportSerializer(ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "user", "period", "account_type", "created_at"]
        read_only_fields = ["user", "created_at"]


class ReportDetailsSerializer(ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "user", "period", "account_type", "created_at"]

    # I am doing it this way after reading the discussion here:
    # https://github.com/em1208/adrf/issues/27
    async def ato_representation(self, instance):
        representation = super().to_representation(instance)
        accounts = await sync_to_async(list)(
            AccountValue.objects.filter(report=instance).all()
        )
        account_balances = await AccountValueSerializer(accounts, many=True).adata
        representation["account_balances"] = account_balances
        return representation
