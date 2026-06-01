import logging

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework_jwt.authentication import BaseJSONWebTokenAuthentication

logger = logging.getLogger('app.logger')


def get_or_create_localdev_user():
    username = getattr(settings, 'LOCAL_DEV_USER', 'localdev')

    try:
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                'email': '{}@local.invalid'.format(username),
                'is_staff': True,
                'is_superuser': True,
            },
        )
    except Exception as e:
        logger.warning("Local dev auth could not create or load %s: %s", username, e)
        return None

    changed = False
    if not user.is_staff:
        user.is_staff = True
        changed = True
    if not user.is_superuser:
        user.is_superuser = True
        changed = True
    if changed:
        user.save(update_fields=['is_staff', 'is_superuser'])

    return user


class LocalDevAuthentication(authentication.BaseAuthentication):
    """
    Authenticate all local-dev API requests as a disposable superuser.

    This is only enabled when settings.LOCAL_DEV_SKIP_AUTH is true. The setting
    is guarded by DEBUG and an explicit local-dev environment flag.
    """

    def authenticate(self, request):
        if not getattr(settings, 'LOCAL_DEV_SKIP_AUTH', False):
            return None

        user = get_or_create_localdev_user()
        if user is None:
            return None

        return (user, None)


class JSONWebTokenAuthenticationQS(BaseJSONWebTokenAuthentication):
    def get_jwt_value(self, request):
         return request.query_params.get('jwt')
