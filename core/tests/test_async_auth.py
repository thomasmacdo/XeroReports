import pytest
from django.test import RequestFactory
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import AccessToken

from core.authentication import AsyncJWTAuthentication
from core.tests.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.asyncio]

factory = RequestFactory()


class TestAsyncJWTAuthentication:
    async def test_successful_authentication(self):
        user = await UserFactory.acreate()
        token = AccessToken.for_user(user)
        request = factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {str(token)}"

        auth = AsyncJWTAuthentication()
        authenticated_user, validated_token = await auth.authenticate(request)

        assert authenticated_user.id == user.id
        assert validated_token.payload == token.payload

    async def test_invalid_token(self):
        request = factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_token"

        auth = AsyncJWTAuthentication()
        with pytest.raises(InvalidToken):
            await auth.authenticate(request)

    async def test_missing_authorization_header(self):
        request = factory.get("/")

        auth = AsyncJWTAuthentication()
        result = await auth.authenticate(request)

        assert result is None

    async def test_non_existent_user(self):
        user = await UserFactory.acreate()
        token = AccessToken.for_user(user)

        await user.adelete()

        request = factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {str(token)}"

        auth = AsyncJWTAuthentication()
        with pytest.raises(InvalidToken, match="User not found"):
            await auth.authenticate(request)
