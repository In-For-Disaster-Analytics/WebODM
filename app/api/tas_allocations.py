import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.services.tas_allocations import (
    TASConfigurationError,
    choose_default_allocation,
    list_active_allocations,
)

logger = logging.getLogger('app.logger')


class TASAllocationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            allocations = list_active_allocations(request.user.username)
            return Response({
                'allocations': allocations,
                'default': choose_default_allocation(allocations)
            })
        except TASConfigurationError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception('Could not fetch TAS allocations for user %s', request.user.username)
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
