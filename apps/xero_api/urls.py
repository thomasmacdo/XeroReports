from apps.xero_api.views import XeroConnectView, XeroCallbackView
from django.urls import path

urlpatterns = [
    path("connect/", XeroConnectView.as_view(), name="xero_connect"),
    path("callback/", XeroCallbackView.as_view(), name="xero_callback"),
]
