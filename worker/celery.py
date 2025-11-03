import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webodm.settings')

# Import Django and configure it first
import django
django.setup()

from celery import Celery

# Create Celery app with basic config first to allow imports
app = Celery('tasks')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Now it's safe to import modules that may need the Celery app
try:
    app.autodiscover_tasks()
except Exception as e:
    print(f"Warning: Task autodiscovery failed: {e}")

# Explicitly import app-specific task modules 
try:
    import app.tasks.tapis_storage  # noqa: F401
except Exception as e:
    print(f"Warning: Failed to import tapis_storage tasks: {e}")

# Configure Celery AFTER imports are done
app.conf.result_backend_transport_options = {
    'retry_policy': {
       'timeout': 5.0
    }
}

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

# Mock class for handling async results during testing
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

if __name__ == '__main__':
    app.start()