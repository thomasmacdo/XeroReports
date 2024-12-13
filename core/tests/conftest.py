import logging

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import authenticate
from django.test.client import RequestFactory

from core.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def setup_logging(caplog):
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    return caplog


@pytest.fixture
@pytest.mark.asyncio
async def authenticated_user():
    user = await UserFactory.acreate(is_superuser=False)
    raw_password = "securepassword"
    user.set_password(raw_password)
    await sync_to_async(user.save)()

    request = RequestFactory().post("api/token/")
    authenticated_user = await sync_to_async(authenticate)(
        request=request, username=user.username, password=raw_password
    )
    return authenticated_user
