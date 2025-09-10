import logging
import requests
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
from django.conf import settings
from django.contrib.auth.models import User
from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
from app.models.project import Project
from app.models import Task
import tempfile
import os
from datetime import datetime, timedelta

logger = logging.getLogger('app.logger')


class TapisStorageService:
    """
    Service for discovering and accessing Tapis storage systems
    to automatically create WebODM projects from flight data
    """
    
    def __init__(self, user: User, client: TapisOAuth2Client):
        self.user = user
        self.client = client
        self.token = self._get_valid_token()
        self.base_url = client.base_url.rstrip('/')
        
    def _get_valid_token(self) -> TapisOAuth2Token:
        """Get a valid access token for the user"""
        try:
            token = TapisOAuth2Token.objects.get(user=self.user, client=self.client)
            if not token.is_valid:
                raise ValueError("Token is expired or invalid")
            return token
        except TapisOAuth2Token.DoesNotExist:
            raise ValueError(f"No Tapis token found for user {self.user.username}")
    
    def _make_request(self, endpoint: str, method: str = 'GET', **kwargs) -> Dict:
        """Make authenticated request to Tapis API"""
        url = urljoin(self.base_url + '/', endpoint)
        headers = {
            'Authorization': f'Bearer {self.token.access_token}',
            'Content-Type': 'application/json',
            'X-Tapis-Tenant': self.client.tenant_id
        }
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Tapis API request failed: {e}")
            raise
    
    def discover_project_systems(self) -> List[Dict]:
        """
        Discover all ptdatax.project.* systems the user has access to
        """
        try:
            # Search for systems matching ptdatax.project.* pattern
            search_params = {
                'search': 'id.like.ptdatax.project.*',
                'limit': 1000,  # Adjust as needed
                'select': 'id,host,systemType,description,created,updated'
            }
            
            result = self._make_request('v3/systems', params=search_params)
            systems = result.get('result', [])
            
            logger.info(f"Found {len(systems)} ptdatax.project.* systems for user {self.user.username}")
            return systems
            
        except Exception as e:
            logger.error(f"Failed to discover project systems: {e}")
            return []
    
    def scan_system_for_flights(self, system_id: str) -> List[Dict]:
        """
        Scan a Tapis system for directories matching <Flight>/code/images/*.jpg pattern
        
        Returns list of flight info dictionaries with:
        - flight_name: Name of the flight directory
        - system_id: Tapis system ID
        - images_path: Path to images directory
        - image_count: Number of JPG images found
        """
        flights = []
        
        try:
            # List root directory of the system
            root_listing = self._make_request(f'v3/files/ops/{system_id}/')
            
            for item in root_listing.get('result', []):
                if item.get('type') == 'dir':
                    flight_name = item.get('name')
                    if flight_name:
                        flight_info = self._check_flight_directory(system_id, flight_name)
                        if flight_info:
                            flights.append(flight_info)
                            
        except Exception as e:
            logger.error(f"Failed to scan system {system_id}: {e}")
            
        return flights
    
    def _check_flight_directory(self, system_id: str, flight_name: str) -> Optional[Dict]:
        """
        Check if a flight directory has the required structure: <Flight>/code/images/*.jpg
        """
        try:
            # Check for code directory
            code_path = f'{flight_name}/code'
            try:
                code_listing = self._make_request(f'v3/files/ops/{system_id}/{code_path}/')
            except requests.RequestException:
                # No code directory found
                return None
                
            # Check for images directory within code
            has_images_dir = False
            for item in code_listing.get('result', []):
                if item.get('type') == 'dir' and item.get('name') == 'images':
                    has_images_dir = True
                    break
                    
            if not has_images_dir:
                return None
                
            # Count JPG images in the images directory
            images_path = f'{flight_name}/code/images'
            try:
                images_listing = self._make_request(f'v3/files/ops/{system_id}/{images_path}/')
                jpg_count = sum(1 for item in images_listing.get('result', []) 
                              if item.get('type') == 'file' and 
                              item.get('name', '').lower().endswith(('.jpg', '.jpeg')))
                
                if jpg_count > 0:
                    return {
                        'flight_name': flight_name,
                        'system_id': system_id,
                        'images_path': images_path,
                        'image_count': jpg_count,
                        'discovered_at': datetime.now()
                    }
                    
            except requests.RequestException:
                logger.warning(f"Could not access images directory in {system_id}:{images_path}")
                
        except Exception as e:
            logger.error(f"Error checking flight directory {flight_name} in system {system_id}: {e}")
            
        return None
    
    def create_project_from_flight(self, flight_info: Dict) -> Optional[Project]:
        """
        Create a WebODM project from discovered flight data
        """
        try:
            # Create project
            project_name = f"{flight_info['flight_name']} ({flight_info['system_id']})"
            project_description = (
                f"Auto-created from Tapis system {flight_info['system_id']}\n"
                f"Flight: {flight_info['flight_name']}\n"
                f"Images path: {flight_info['images_path']}\n"
                f"Image count: {flight_info['image_count']}\n"
                f"Discovered: {flight_info['discovered_at']}"
            )
            
            project = Project.objects.create(
                owner=self.user,
                name=project_name,
                description=project_description,
                tags=f"tapis,flight,{flight_info['system_id']},{flight_info['flight_name']}"
            )
            
            logger.info(f"Created WebODM project {project.id} for flight {flight_info['flight_name']}")
            
            # Create a task for the flight images
            task = self._create_task_for_flight(project, flight_info)
            if task:
                logger.info(f"Created task {task.id} for project {project.id}")
            
            return project
            
        except Exception as e:
            logger.error(f"Failed to create project from flight {flight_info}: {e}")
            return None
    
    def _create_task_for_flight(self, project: Project, flight_info: Dict) -> Optional[Task]:
        """
        Create a WebODM task with images from the flight directory
        """
        try:
            # Create task
            task = Task.objects.create(
                project=project,
                name=f"Flight {flight_info['flight_name']}",
                processing_node=None,  # Will be assigned automatically
                options={},
                import_url=f"tapis://{flight_info['system_id']}/{flight_info['images_path']}"
            )
            
            # Schedule image download and processing
            # This would typically be handled by a Celery task
            self._schedule_image_download(task, flight_info)
            
            return task
            
        except Exception as e:
            logger.error(f"Failed to create task for flight {flight_info}: {e}")
            return None
    
    def _schedule_image_download(self, task: Task, flight_info: Dict):
        """
        Schedule downloading images from Tapis to WebODM task directory
        This should be implemented as an async Celery task
        """
        # TODO: Implement async image download
        # For now, just log the action
        logger.info(f"Scheduled image download for task {task.id} from {flight_info['system_id']}:{flight_info['images_path']}")
    
    def download_flight_images(self, task: Task, flight_info: Dict) -> bool:
        """
        Download images from Tapis system to WebODM task directory
        """
        try:
            # Get task directory
            task_dir = task.get_task_dir()
            os.makedirs(task_dir, exist_ok=True)
            
            # List images in the flight directory
            images_path = flight_info['images_path']
            system_id = flight_info['system_id']
            
            images_listing = self._make_request(f'v3/files/ops/{system_id}/{images_path}/')
            
            downloaded_count = 0
            for item in images_listing.get('result', []):
                if item.get('type') == 'file' and item.get('name', '').lower().endswith(('.jpg', '.jpeg')):
                    filename = item.get('name')
                    if self._download_single_image(system_id, f"{images_path}/{filename}", 
                                                 os.path.join(task_dir, filename)):
                        downloaded_count += 1
            
            logger.info(f"Downloaded {downloaded_count} images for task {task.id}")
            return downloaded_count > 0
            
        except Exception as e:
            logger.error(f"Failed to download images for task {task.id}: {e}")
            return False
    
    def _download_single_image(self, system_id: str, remote_path: str, local_path: str) -> bool:
        """
        Download a single image file from Tapis system
        """
        try:
            # Use Tapis Files API to download the file
            url = f"{self.base_url}/v3/files/content/{system_id}/{remote_path}"
            headers = {
                'Authorization': f'Bearer {self.token.access_token}',
                'X-Tapis-Tenant': self.client.tenant_id
            }
            
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {e}")
            return False


class TapisFlightDiscoveryService:
    """
    High-level service for discovering and creating projects from Tapis flight data
    """
    
    @classmethod
    def discover_and_create_projects(cls, user: User, client: TapisOAuth2Client) -> Dict[str, any]:
        """
        Discover all available flight data and create WebODM projects
        
        Returns summary of discovery and creation results
        """
        storage_service = TapisStorageService(user, client)
        
        results = {
            'systems_scanned': 0,
            'flights_discovered': 0,
            'projects_created': 0,
            'errors': [],
            'created_projects': []
        }
        
        try:
            # Discover project systems
            systems = storage_service.discover_project_systems()
            results['systems_scanned'] = len(systems)
            
            all_flights = []
            
            # Scan each system for flights
            for system in systems:
                system_id = system.get('id')
                if system_id:
                    try:
                        flights = storage_service.scan_system_for_flights(system_id)
                        all_flights.extend(flights)
                        logger.info(f"Found {len(flights)} flights in system {system_id}")
                    except Exception as e:
                        error_msg = f"Failed to scan system {system_id}: {e}"
                        results['errors'].append(error_msg)
                        logger.error(error_msg)
            
            results['flights_discovered'] = len(all_flights)
            
            # Create projects for each flight
            for flight_info in all_flights:
                try:
                    # Check if project already exists
                    existing_project = cls._find_existing_project(user, flight_info)
                    if existing_project:
                        logger.info(f"Project already exists for {flight_info['flight_name']} in {flight_info['system_id']}")
                        continue
                    
                    project = storage_service.create_project_from_flight(flight_info)
                    if project:
                        results['projects_created'] += 1
                        results['created_projects'].append({
                            'project_id': project.id,
                            'project_name': project.name,
                            'flight_name': flight_info['flight_name'],
                            'system_id': flight_info['system_id'],
                            'image_count': flight_info['image_count']
                        })
                
                except Exception as e:
                    error_msg = f"Failed to create project for flight {flight_info['flight_name']}: {e}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
        except Exception as e:
            error_msg = f"Discovery process failed: {e}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
        
        return results
    
    @classmethod
    def _find_existing_project(cls, user: User, flight_info: Dict) -> Optional[Project]:
        """
        Check if a project already exists for this flight
        """
        flight_tag = f"{flight_info['system_id']},{flight_info['flight_name']}"
        return Project.objects.filter(
            owner=user,
            tags__icontains=flight_tag
        ).first()