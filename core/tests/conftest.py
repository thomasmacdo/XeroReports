from datetime import date
import pytest
from apps.reports.models import AccountValue, Report
from core.tests.factories import UserFactory
from django.contrib.auth import authenticate
from django.test.client import RequestFactory
import logging


@pytest.fixture(autouse=True)
def setup_logging(caplog):
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    return caplog


@pytest.fixture
def authenticated_user():
    user = UserFactory.create(username="testuser", is_superuser=False)
    raw_password = "securepassword"
    user.set_password(raw_password)
    user.save()

    request = RequestFactory().post("api/token/")

    authenticated_user = authenticate(
        request=request, username=user.username, password=raw_password
    )
    return authenticated_user


@pytest.fixture
def admin_user():
    return UserFactory.create(username="admin", is_superuser=True)


@pytest.fixture
def mock_token_response():
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 1800,
        "token_type": "Bearer",
    }


@pytest.fixture
def report_factory(db, factory):
    class ReportFactoryClass(factory.django.DjangoModelFactory):
        class Meta:
            model = Report

        user = factory.SubFactory(UserFactory)
        period = factory.LazyFunction(lambda: date(2023, 1, 1))
        account_type = "ASSET"

    return ReportFactoryClass


@pytest.fixture
def account_value_factory(db, factory):
    class AccountValueFactoryClass(factory.django.DjangoModelFactory):
        class Meta:
            model = AccountValue

        report = factory.SubFactory(report_factory)
        xero_account_id = factory.Sequence(lambda n: f"acc-{n}")
        account_name = factory.Sequence(lambda n: f"Account {n}")
        account_balance = 100.00

    return AccountValueFactoryClass


@pytest.fixture
def mock_xero_connections():
    return [
        {
            "tenantId": "test_tenant",
            "authEventId": "test_event",
            "tenantType": "ORGANISATION",
            "tenantName": "Test Org",
        }
    ]
