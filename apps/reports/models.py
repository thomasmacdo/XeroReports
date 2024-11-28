from django.db import models
from django.contrib.auth.models import User


class Report(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text="User who created the report"
    )
    period = models.DateField(help_text="The reporting period (first day of the month)")
    account_type = models.CharField(
        max_length=50, help_text="Type of accounts included in the report"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the report was created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]


class AccountValue(models.Model):
    id = models.BigAutoField(primary_key=True)
    report = models.ForeignKey(
        Report, related_name="account_balances", on_delete=models.CASCADE
    )
    account_name = models.CharField(max_length=255)
    xero_account_id = models.CharField(max_length=255)
    account_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    class Meta:
        indexes = [
            models.Index(fields=["report", "xero_account_id"]),
        ]
