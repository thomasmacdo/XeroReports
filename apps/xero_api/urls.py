from django.urls import path

from apps.xero_api.views import XeroCallbackView, XeroConnectView

urlpatterns = [
    path("connect/", XeroConnectView.as_view(), name="xero_connect"),
    path("callback/", XeroCallbackView.as_view(), name="xero_callback"),
]
