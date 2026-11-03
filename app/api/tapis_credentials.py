import logging

from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from app.services.tapis_credentials import (
    CODE_MISCONFIGURED,
    STATUS_UNKNOWN,
    create_credential_for_user,
    default_system_id,
    get_credential_status,
    is_valid_system_id,
)

logger = logging.getLogger('app.logger')

REFRESH_MIN_INTERVAL_SECONDS = 15
CREATE_LOCK_SECONDS = 30


class HpcAccessGetThrottle(UserRateThrottle):
    scope = 'hpc_access_get'

    def allow_request(self, request, view):
        if request.method != 'GET':
            return True
        return super().allow_request(request, view)


class HpcAccessPostThrottle(UserRateThrottle):
    scope = 'hpc_access_post'

    def allow_request(self, request, view):
        if request.method != 'POST':
            return True
        return super().allow_request(request, view)


class HpcAccessView(APIView):
    """
    GET  /api/tapis/hpc-access/  -> does the signed-in user have a Tapis credential on the
                                    execution system? Always HTTP 200; ``status`` is
                                    ready | missing | unknown and ``unknown`` never blocks.
    POST /api/tapis/hpc-access/  -> ask Tapis to create TMS keys for the user. Only runs
                                    after a fresh probe reports ``missing``.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [HpcAccessGetThrottle, HpcAccessPostThrottle]

    def _system_id(self, request):
        requested = (request.query_params.get('system_id') or '').strip()
        if not requested:
            return default_system_id(), None
        if not is_valid_system_id(requested):
            return None, Response({
                'system_id': requested[:64],
                'status': STATUS_UNKNOWN,
                'code': CODE_MISCONFIGURED,
                'detail': 'Invalid system id.',
            }, status=status.HTTP_400_BAD_REQUEST)
        return requested, None

    def get(self, request):
        system_id, error = self._system_id(request)
        if error:
            return error

        refresh = str(request.query_params.get('refresh', '')).lower() in ('1', 'true', 'yes')
        if refresh:
            # Honour a forced re-check at most once per interval per user.
            refresh = cache.add('hpc:refresh:{}'.format(request.user.pk), 1, REFRESH_MIN_INTERVAL_SECONDS)

        return Response(get_credential_status(request.user, system_id, refresh=refresh))

    def post(self, request):
        system_id, error = self._system_id(request)
        if error:
            return error

        lock_key = 'hpc:lock:{}'.format(request.user.pk)
        if not cache.add(lock_key, 1, CREATE_LOCK_SECONDS):
            return Response({
                'system_id': system_id,
                'status': STATUS_UNKNOWN,
                'code': 'in_progress',
                'detail': 'A credential request is already in progress.',
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            http_status, payload = create_credential_for_user(request.user, system_id)
        finally:
            cache.delete(lock_key)

        return Response(payload, status=http_status)
