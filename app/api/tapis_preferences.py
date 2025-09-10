from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.translation import gettext as _
import logging

from app.models.tapis_preferences import TapisUserPreferences

logger = logging.getLogger('app.logger')


class TapisUserPreferencesView(APIView):
    """
    API endpoint for managing user Tapis preferences
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get current user's Tapis preferences
        
        GET /api/tapis-preferences/
        """
        try:
            preferences = TapisUserPreferences.get_or_create_for_user(request.user)
            
            return Response({
                'success': True,
                'preferences': {
                    'auto_discover_on_login': preferences.auto_discover_on_login,
                    'max_projects_per_discovery': preferences.max_projects_per_discovery,
                    'discovery_cooldown_hours': preferences.discovery_cooldown_hours,
                    'notify_on_discovery_complete': preferences.notify_on_discovery_complete,
                    'notify_on_discovery_errors': preferences.notify_on_discovery_errors,
                    'preferred_systems': preferences.get_preferred_systems_list(),
                    'last_auto_discovery': preferences.last_auto_discovery.isoformat() if preferences.last_auto_discovery else None,
                    'can_run_discovery': preferences.should_run_auto_discovery()
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to get Tapis preferences for user {request.user.username}: {e}")
            return Response({
                'success': False,
                'error': _('Failed to retrieve preferences'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """
        Update user's Tapis preferences
        
        POST /api/tapis-preferences/
        Body: {
            "auto_discover_on_login": true,
            "max_projects_per_discovery": 50,
            "discovery_cooldown_hours": 24,
            "notify_on_discovery_complete": true,
            "notify_on_discovery_errors": true,
            "preferred_systems": ["ptdatax.project.system1", "ptdatax.project.system2"]
        }
        """
        try:
            preferences = TapisUserPreferences.get_or_create_for_user(request.user)
            
            # Update preferences from request data
            if 'auto_discover_on_login' in request.data:
                preferences.auto_discover_on_login = bool(request.data['auto_discover_on_login'])
            
            if 'max_projects_per_discovery' in request.data:
                max_projects = int(request.data['max_projects_per_discovery'])
                if max_projects < 1:
                    return Response({
                        'success': False,
                        'error': _('max_projects_per_discovery must be at least 1')
                    }, status=status.HTTP_400_BAD_REQUEST)
                preferences.max_projects_per_discovery = max_projects
            
            if 'discovery_cooldown_hours' in request.data:
                cooldown_hours = int(request.data['discovery_cooldown_hours'])
                if cooldown_hours < 0:
                    return Response({
                        'success': False,
                        'error': _('discovery_cooldown_hours must be non-negative')
                    }, status=status.HTTP_400_BAD_REQUEST)
                preferences.discovery_cooldown_hours = cooldown_hours
            
            if 'notify_on_discovery_complete' in request.data:
                preferences.notify_on_discovery_complete = bool(request.data['notify_on_discovery_complete'])
            
            if 'notify_on_discovery_errors' in request.data:
                preferences.notify_on_discovery_errors = bool(request.data['notify_on_discovery_errors'])
            
            if 'preferred_systems' in request.data:
                systems = request.data['preferred_systems']
                if isinstance(systems, list):
                    # Validate system IDs
                    for system_id in systems:
                        if not isinstance(system_id, str) or not system_id.startswith('ptdatax.project.'):
                            return Response({
                                'success': False,
                                'error': _('All preferred systems must be ptdatax.project.* system IDs')
                            }, status=status.HTTP_400_BAD_REQUEST)
                    
                    preferences.preferred_systems = ','.join(systems)
                else:
                    return Response({
                        'success': False,
                        'error': _('preferred_systems must be an array of system IDs')
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            preferences.save()
            
            logger.info(f"Updated Tapis preferences for user {request.user.username}")
            
            return Response({
                'success': True,
                'message': _('Preferences updated successfully'),
                'preferences': {
                    'auto_discover_on_login': preferences.auto_discover_on_login,
                    'max_projects_per_discovery': preferences.max_projects_per_discovery,
                    'discovery_cooldown_hours': preferences.discovery_cooldown_hours,
                    'notify_on_discovery_complete': preferences.notify_on_discovery_complete,
                    'notify_on_discovery_errors': preferences.notify_on_discovery_errors,
                    'preferred_systems': preferences.get_preferred_systems_list(),
                    'last_auto_discovery': preferences.last_auto_discovery.isoformat() if preferences.last_auto_discovery else None,
                    'can_run_discovery': preferences.should_run_auto_discovery()
                }
            })
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': _('Invalid data type in request'),
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to update Tapis preferences for user {request.user.username}: {e}")
            return Response({
                'success': False,
                'error': _('Failed to update preferences'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TapisDiscoveryControlView(APIView):
    """
    API endpoint for manual discovery control
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def trigger_discovery(self, request):
        """
        Manually trigger flight discovery, bypassing cooldown and preference checks
        
        POST /api/tapis-discovery/trigger/
        """
        try:
            from app.models.oauth2 import TapisOAuth2Client
            from app.services.tapis_storage import TapisFlightDiscoveryService
            
            # Get active client
            client = TapisOAuth2Client.objects.filter(is_active=True).first()
            if not client:
                return Response({
                    'success': False,
                    'error': _('No active Tapis OAuth2 client found')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user has valid token
            from app.models.oauth2 import TapisOAuth2Token
            try:
                token = TapisOAuth2Token.objects.get(user=request.user, client=client)
                if not token.is_valid:
                    return Response({
                        'success': False,
                        'error': _('Tapis token expired. Please re-authenticate.')
                    }, status=status.HTTP_401_UNAUTHORIZED)
            except TapisOAuth2Token.DoesNotExist:
                return Response({
                    'success': False,
                    'error': _('No Tapis token found. Please authenticate first.')
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Run discovery
            try:
                from app.tasks.tapis_storage import discover_and_create_flight_projects
                
                # Try async first
                result = discover_and_create_flight_projects.delay(
                    user_id=request.user.id,
                    client_id=client.client_id
                )
                
                # Update last discovery timestamp
                preferences = TapisUserPreferences.get_or_create_for_user(request.user)
                preferences.update_last_discovery()
                
                return Response({
                    'success': True,
                    'message': _('Flight discovery started'),
                    'task_id': str(result.id)
                })
                
            except ImportError:
                # Fallback to synchronous
                logger.warning("Celery not available, running synchronous discovery")
                
                results = TapisFlightDiscoveryService.discover_and_create_projects(request.user, client)
                
                # Update last discovery timestamp
                preferences = TapisUserPreferences.get_or_create_for_user(request.user)
                preferences.update_last_discovery()
                
                return Response({
                    'success': True,
                    'message': _('Flight discovery completed'),
                    'results': results
                })
                
        except Exception as e:
            logger.error(f"Failed to trigger manual discovery for user {request.user.username}: {e}")
            return Response({
                'success': False,
                'error': _('Failed to trigger discovery'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)