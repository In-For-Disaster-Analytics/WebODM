from celery import task
from celery.utils.log import get_task_logger
from django.contrib.auth.models import User
from app.models.oauth2 import TapisOAuth2Client
from app.models import Task, Project
from app.services.tapis_storage import TapisStorageService, TapisFlightDiscoveryService

logger = get_task_logger(__name__)


@task
def discover_and_create_flight_projects(user_id: int, client_id: str = None):
    """
    Celery task to discover flight directories and create WebODM projects
    """
    try:
        user = User.objects.get(id=user_id)
        
        if client_id:
            client = TapisOAuth2Client.objects.get(client_id=client_id, is_active=True)
        else:
            client = TapisOAuth2Client.objects.filter(is_active=True).first()
            
        if not client:
            raise ValueError("No active Tapis OAuth2 client found")
        
        logger.info(f"Starting flight discovery for user {user.username} with client {client.name}")
        
        results = TapisFlightDiscoveryService.discover_and_create_projects(user, client)
        
        logger.info(f"Discovery completed: {results['projects_created']} projects created from {results['flights_discovered']} flights")
        
        return results
        
    except Exception as e:
        logger.error(f"Flight discovery task failed: {e}")
        raise


@task
def download_flight_images(task_id: int, flight_info: dict):
    """
    Celery task to download images from Tapis system to WebODM task directory
    """
    try:
        task_obj = Task.objects.get(id=task_id)
        user = task_obj.project.owner
        
        # Get first active Tapis client
        client = TapisOAuth2Client.objects.filter(is_active=True).first()
        if not client:
            raise ValueError("No active Tapis OAuth2 client found")
        
        storage_service = TapisStorageService(user, client)
        
        logger.info(f"Starting image download for task {task_id} from {flight_info['system_id']}:{flight_info['images_path']}")
        
        success = storage_service.download_flight_images(task_obj, flight_info)
        
        if success:
            logger.info(f"Successfully downloaded images for task {task_id}")
            # Update task status or trigger processing
            # This would depend on your WebODM task processing workflow
        else:
            logger.error(f"Failed to download images for task {task_id}")
            
        return success
        
    except Exception as e:
        logger.error(f"Image download task failed: {e}")
        raise


@task
def sync_all_flight_projects(user_id: int, client_id: str = None):
    """
    Celery task to sync images for all flight projects belonging to a user
    """
    try:
        user = User.objects.get(id=user_id)
        
        if client_id:
            client = TapisOAuth2Client.objects.get(client_id=client_id, is_active=True)
        else:
            client = TapisOAuth2Client.objects.filter(is_active=True).first()
            
        if not client:
            raise ValueError("No active Tapis OAuth2 client found")
        
        # Find all Tapis flight projects for the user
        flight_projects = Project.objects.filter(
            owner=user,
            tags__icontains='tapis'
        )
        
        logger.info(f"Starting sync for {flight_projects.count()} flight projects")
        
        storage_service = TapisStorageService(user, client)
        synced_count = 0
        
        for project in flight_projects:
            try:
                # Extract flight info from project tags
                tags = project.tags.split(',') if project.tags else []
                system_id = None
                flight_name = None
                
                for tag in tags:
                    tag = tag.strip()
                    if tag.startswith('ptdatax.project'):
                        system_id = tag
                    elif tag not in ['tapis', 'flight']:
                        flight_name = tag
                
                if system_id and flight_name:
                    task_obj = project.task_set.first()
                    if task_obj:
                        flight_info = {
                            'system_id': system_id,
                            'flight_name': flight_name,
                            'images_path': f'{flight_name}/code/images'
                        }
                        
                        success = storage_service.download_flight_images(task_obj, flight_info)
                        if success:
                            synced_count += 1
                            logger.info(f"Synced project {project.id}: {project.name}")
                        else:
                            logger.warning(f"Failed to sync project {project.id}: {project.name}")
                
            except Exception as e:
                logger.error(f"Error syncing project {project.id}: {e}")
                continue
        
        logger.info(f"Sync completed: {synced_count} of {flight_projects.count()} projects synced")
        
        return {
            'total_projects': flight_projects.count(),
            'synced_projects': synced_count
        }
        
    except Exception as e:
        logger.error(f"Sync all flight projects task failed: {e}")
        raise


@task
def cleanup_expired_oauth_states():
    """
    Periodic task to clean up expired OAuth2 state objects
    """
    try:
        from app.models.oauth2 import TapisOAuth2State
        TapisOAuth2State.cleanup_expired()
        logger.info("Cleaned up expired OAuth2 states")
    except Exception as e:
        logger.error(f"Failed to cleanup expired OAuth2 states: {e}")
        raise


@task
def periodic_flight_discovery(user_id: int = None, client_id: str = None):
    """
    Periodic task to discover new flights and create projects
    Can be run for a specific user or all users with valid Tapis tokens
    """
    try:
        if user_id:
            # Run for specific user
            users = [User.objects.get(id=user_id)]
        else:
            # Run for all users with valid Tapis tokens
            from app.models.oauth2 import TapisOAuth2Token
            users = User.objects.filter(
                tapis_oauth2_tokens__isnull=False
            ).distinct()
        
        if client_id:
            client = TapisOAuth2Client.objects.get(client_id=client_id, is_active=True)
        else:
            client = TapisOAuth2Client.objects.filter(is_active=True).first()
            
        if not client:
            raise ValueError("No active Tapis OAuth2 client found")
        
        total_results = {
            'users_processed': 0,
            'total_projects_created': 0,
            'total_flights_discovered': 0,
            'errors': []
        }
        
        for user in users:
            try:
                logger.info(f"Running periodic discovery for user {user.username}")
                
                results = TapisFlightDiscoveryService.discover_and_create_projects(user, client)
                
                total_results['users_processed'] += 1
                total_results['total_projects_created'] += results['projects_created']
                total_results['total_flights_discovered'] += results['flights_discovered']
                total_results['errors'].extend(results['errors'])
                
            except Exception as e:
                error_msg = f"Failed periodic discovery for user {user.username}: {e}"
                total_results['errors'].append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Periodic discovery completed: {total_results}")
        
        return total_results
        
    except Exception as e:
        logger.error(f"Periodic flight discovery task failed: {e}")
        raise