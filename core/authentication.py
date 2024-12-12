from asgiref.sync import sync_to_async
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings


class AsyncJWTAuthentication(JWTAuthentication):
    async def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = await sync_to_async(self.get_validated_token)(raw_token)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        user = await self.get_user_async(validated_token)
        return (user, validated_token)

    async def get_user_async(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            UserModel = self.user_model
            user = await UserModel.objects.aget(id=user_id)
        except UserModel.DoesNotExist:
            raise InvalidToken(_("User not found"), code="user_not_found")

        return user
