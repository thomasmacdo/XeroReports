from django.contrib.auth.models import User
from django.db import models


class XeroToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class XeroTenant(models.Model):
    tenant_id = models.CharField(max_length=128)
    auth_event_id = models.CharField(max_length=128)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tenant_type = models.CharField(max_length=128)
    tenant_name = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)


class XeroAuthState(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    state = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
