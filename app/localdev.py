import logging

from django.conf import settings
from django.contrib.auth import login

from app.api.authentication import get_or_create_localdev_user

logger = logging.getLogger('app.logger')


class LocalDevLoginMiddleware:
    """
    Create a browser session for the disposable local-dev user.

    This middleware is only inserted when settings.LOCAL_DEV_SKIP_AUTH is true,
    which is guarded by DEBUG and WO_LOCAL_DEV_SKIP_AUTH=YES.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'LOCAL_DEV_SKIP_AUTH', False):
            request_user = getattr(request, 'user', None)
            if request_user is None or not request_user.is_authenticated:
                user = get_or_create_localdev_user()
                if user is not None:
                    login(request, user, backend='app.auth.tapis_oauth2.TapisOAuth2Backend')
                    request.user = user
                else:
                    logger.warning("Local dev browser login skipped; no local user was available.")

        return self.get_response(request)
