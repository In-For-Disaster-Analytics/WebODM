from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.http import Http404
from django.utils.translation import gettext as _
import logging

from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
from app.services.tapis_storage import TapisStorageService, TapisFlightDiscoveryService
from app.models.project import Project

logger = logging.getLogger('app.logger')


class TapisStorageViewSet(viewsets.ViewSet):
    """
    API endpoints for Tapis storage integration and flight discovery
    """
    permission_classes = [IsAuthenticated]
    
    def _get_tapis_client(self, client_id: str = None) -> TapisOAuth2Client:
        """Get active Tapis OAuth2 client"""
        if client_id:
            try:
                return TapisOAuth2Client.objects.get(client_id=client_id, is_active=True)
            except TapisOAuth2Client.DoesNotExist:
                raise Http404(f"Tapis client {client_id} not found")
        else:
            # Get the first active client
            client = TapisOAuth2Client.objects.filter(is_active=True).first()
            if not client:
                raise Http404("No active Tapis OAuth2 client found")
            return client
    
    def _check_user_token(self, client: TapisOAuth2Client):
        """Check if user has valid Tapis token"""
        try:
            token = TapisOAuth2Token.objects.get(user=self.request.user, client=client)
            if not token.is_valid:
                raise ValueError("Token expired")
            return token
        except TapisOAuth2Token.DoesNotExist:
            raise ValueError("No Tapis token found")
    
    @action(detail=False, methods=['get'])
    def systems(self, request):
        """
        List available ptdatax.project.* systems for the authenticated user
        
        GET /api/tapis-storage/systems/
        """
        try:
            client = self._get_tapis_client()
            self._check_user_token(client)
            
            storage_service = TapisStorageService(request.user, client)
            systems = storage_service.discover_project_systems()
            
            return Response({
                'success': True,
                'systems': systems,
                'count': len(systems)
            })
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e),
                'detail': _('Please authenticate with Tapis first')
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Failed to list Tapis systems: {e}")
            return Response({
                'success': False,
                'error': _('Failed to retrieve systems'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def discover_flights(self, request):
        """
        Discover flight directories across all accessible ptdatax.project.* systems
        
        POST /api/tapis-storage/discover-flights/
        Optional body: {"systems": ["system_id1", "system_id2"]} to limit scan
        """
        try:
            client = self._get_tapis_client()
            self._check_user_token(client)
            
            storage_service = TapisStorageService(request.user, client)
            
            # Get systems to scan
            target_systems = request.data.get('systems', [])
            if target_systems:
                # Scan only specified systems
                all_flights = []
                for system_id in target_systems:
                    flights = storage_service.scan_system_for_flights(system_id)
                    all_flights.extend(flights)
            else:
                # Discover and scan all project systems
                systems = storage_service.discover_project_systems()
                all_flights = []
                for system in systems:
                    system_id = system.get('id')
                    if system_id:
                        flights = storage_service.scan_system_for_flights(system_id)
                        all_flights.extend(flights)
            
            return Response({
                'success': True,
                'flights': all_flights,
                'count': len(all_flights)
            })
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e),
                'detail': _('Please authenticate with Tapis first')
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Failed to discover flights: {e}")
            return Response({
                'success': False,
                'error': _('Failed to discover flights'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_projects(self, request):
        """
        Create WebODM projects from discovered flight data
        
        POST /api/tapis-storage/create-projects/
        Body: {
            "flights": [flight_info_objects] or "auto_discover": true
        }
        """
        try:
            client = self._get_tapis_client()
            self._check_user_token(client)
            
            if request.data.get('auto_discover'):
                # Auto-discover and create projects
                results = TapisFlightDiscoveryService.discover_and_create_projects(
                    request.user, client
                )
            else:
                # Create projects from provided flight data
                flights = request.data.get('flights', [])
                if not flights:
                    return Response({
                        'success': False,
                        'error': _('No flights provided')
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                storage_service = TapisStorageService(request.user, client)
                results = {
                    'systems_scanned': 0,
                    'flights_discovered': len(flights),
                    'projects_created': 0,
                    'errors': [],
                    'created_projects': []
                }
                
                for flight_info in flights:
                    try:
                        project = storage_service.create_project_from_flight(flight_info)
                        if project:
                            results['projects_created'] += 1
                            results['created_projects'].append({
                                'project_id': project.id,
                                'project_name': project.name,
                                'flight_name': flight_info['flight_name'],
                                'system_id': flight_info['system_id'],
                                'image_count': flight_info.get('image_count', 0)
                            })
                    except Exception as e:
                        error_msg = f"Failed to create project for {flight_info.get('flight_name', 'unknown')}: {e}"
                        results['errors'].append(error_msg)
                        logger.error(error_msg)
            
            return Response({
                'success': True,
                'results': results
            })
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e),
                'detail': _('Please authenticate with Tapis first')
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Failed to create projects: {e}")
            return Response({
                'success': False,
                'error': _('Failed to create projects'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def flight_projects(self, request):
        """
        List projects created from Tapis flight data
        
        GET /api/tapis-storage/flight-projects/
        """
        try:
            # Find projects with Tapis-related tags
            projects = Project.objects.filter(
                owner=request.user,
                tags__icontains='tapis'
            ).order_by('-created_at')
            
            project_data = []
            for project in projects:
                # Parse flight info from tags and description
                tags = project.tags.split(',') if project.tags else []
                tapis_tags = [tag.strip() for tag in tags if 'ptdatax.project' in tag or tag == 'tapis' or tag == 'flight']
                
                project_data.append({
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'created_at': project.created_at,
                    'tags': tapis_tags,
                    'task_count': project.task_set.count()
                })
            
            return Response({
                'success': True,
                'projects': project_data,
                'count': len(project_data)
            })
            
        except Exception as e:
            logger.error(f"Failed to list flight projects: {e}")
            return Response({
                'success': False,
                'error': _('Failed to retrieve flight projects'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def sync_project_images(self, request):
        """
        Download images for a project created from Tapis flight data
        
        POST /api/tapis-storage/sync-project-images/
        Body: {"project_id": 123}
        """
        try:
            project_id = request.data.get('project_id')
            if not project_id:
                return Response({
                    'success': False,
                    'error': _('Project ID required')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                project = Project.objects.get(id=project_id, owner=request.user)
            except Project.DoesNotExist:
                return Response({
                    'success': False,
                    'error': _('Project not found')
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if this is a Tapis flight project
            if 'tapis' not in project.tags:
                return Response({
                    'success': False,
                    'error': _('This is not a Tapis flight project')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Extract flight info from project tags and description
            # This is a simplified implementation - in production you might
            # want to store this info more systematically
            tags = project.tags.split(',') if project.tags else []
            system_id = None
            flight_name = None
            
            for tag in tags:
                tag = tag.strip()
                if tag.startswith('ptdatax.project'):
                    system_id = tag
                elif tag not in ['tapis', 'flight']:
                    flight_name = tag
            
            if not system_id or not flight_name:
                return Response({
                    'success': False,
                    'error': _('Cannot determine flight information from project')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            client = self._get_tapis_client()
            self._check_user_token(client)
            
            storage_service = TapisStorageService(request.user, client)
            
            # Find the task for this project
            task = project.task_set.first()
            if not task:
                return Response({
                    'success': False,
                    'error': _('No task found for this project')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            flight_info = {
                'system_id': system_id,
                'flight_name': flight_name,
                'images_path': f'{flight_name}/code/images'
            }
            
            # Download images
            success = storage_service.download_flight_images(task, flight_info)
            
            return Response({
                'success': success,
                'message': _('Image sync completed') if success else _('Image sync failed')
            })
            
        except ValueError as e:
            return Response({
                'success': False,
                'error': str(e),
                'detail': _('Please authenticate with Tapis first')
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Failed to sync project images: {e}")
            return Response({
                'success': False,
                'error': _('Failed to sync images'),
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)