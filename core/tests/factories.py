import factory
from faker import Faker
from django.contrib.auth.models import User

from apps.xero_api.models import XeroToken, XeroTenant, XeroAuthState
from apps.reports.models import Report, AccountValue
from apps.xero_api.account_type import AccountType

fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.LazyFunction(lambda: fake.user_name())
    password = factory.LazyFunction(lambda: fake.password(length=12))
    is_superuser = False


class XeroTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = XeroToken

    user = factory.SubFactory(UserFactory)
    token = factory.LazyFunction(
        lambda: {"access": fake.uuid4(), "refresh": fake.uuid4()}
    )


class XeroTenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = XeroTenant

    user = factory.SubFactory(UserFactory)
    tenant_id = factory.LazyFunction(lambda: fake.uuid4())
    tenant_name = factory.LazyFunction(lambda: fake.company())


class XeroAuthStateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = XeroAuthState

    user = factory.SubFactory(UserFactory)
    state = factory.LazyFunction(lambda: fake.sha256())


class ReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Report

    user = factory.SubFactory(UserFactory)
    period = factory.LazyFunction(lambda: fake.date())
    account_type = factory.LazyFunction(
        lambda: fake.random_element(AccountType.__members__.values())
    )
    created_at = factory.LazyFunction(lambda: fake.date_time())


class AccountValueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccountValue

    xero_account_id = factory.LazyFunction(lambda: fake.uuid4())
    report = factory.SubFactory(ReportFactory)
    account_name = factory.LazyFunction(lambda: fake.company())
    account_balance = factory.LazyFunction(
        lambda: fake.pydecimal(left_digits=6, right_digits=2, positive=True)
    )
