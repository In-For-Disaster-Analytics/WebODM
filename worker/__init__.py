"""
WebODM Celery worker initialization
"""
import os
import logging

# Configure logging first
logger = logging.getLogger('worker')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(name)s | %(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webodm.settings')

logger.info("Initializing Celery app...")

# Create celery app
from celery import Celery
app = Celery('webodm')

# Load config from Django settings
logger.info("Loading Celery config from Django settings...")
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configure result backend options
app.conf.result_backend_transport_options = {
    'retry_policy': {
        'timeout': 5.0
    }
}

# Set up scheduled tasks
app.conf.beat_schedule = {
    'update-nodes-info': {
        'task': 'worker.tasks.update_nodes_info',
        'schedule': 30,
        'options': {
            'expires': 14,
            'retry': False
        }
    },
    'cleanup-projects': {
        'task': 'worker.tasks.cleanup_projects',
        'schedule': 60,
        'options': {
            'expires': 29,
            'retry': False
        }
    },
    'cleanup-tasks': {
        'task': 'worker.tasks.cleanup_tasks',
        'schedule': 3600,
        'options': {
            'expires': 1799,
            'retry': False
        }
    },
    'cleanup-tmp-directory': {
        'task': 'worker.tasks.cleanup_tmp_directory',
        'schedule': 3600,
        'options': {
            'expires': 1799,
            'retry': False
        }
    },
    'process-pending-tasks': {
        'task': 'worker.tasks.process_pending_tasks',
        'schedule': 5,
        'options': {
            'expires': 2,
            'retry': False
        }
    },
    'check-quotas': {
        'task': 'worker.tasks.check_quotas',
        'schedule': 3600,
        'options': {
            'expires': 1799,
            'retry': False
        }
    },
}

# For testing only
class MockAsyncResult:
    def __init__(self, celery_task_id, result = None):
        self.celery_task_id = celery_task_id
        self.state = "PENDING"
        if result is None:
            if celery_task_id == 'bogus':
                self.result = None
            else:
                self.result = MockAsyncResult.results.get(celery_task_id)
        else:
            self.result = result
            MockAsyncResult.results[celery_task_id] = result

    def get(self):
        return self.result

    def ready(self):
        return self.result is not None

MockAsyncResult.results = {}
MockAsyncResult.set = lambda cti, r: MockAsyncResult(cti, r)

# Import tasks after app is fully configured
logger.info("Discovering tasks...")
try:
    app.autodiscover_tasks()
    logger.info("Task discovery complete")
except Exception as e:
    logger.warning(f"Task autodiscovery error: {e}")
    # Fall back to explicit imports
    try:
        import app.tasks.tapis_storage
        logger.info("Explicitly imported tapis_storage tasks")
    except Exception as e:
        logger.warning(f"Failed to import tapis_storage tasks: {e}")
