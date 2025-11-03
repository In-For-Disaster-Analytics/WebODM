from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webodm.settings')

app = Celery('tasks')
app.config_from_object('django.conf:settings', namespace='CELERY')
# Ensure Celery discovers tasks defined in Django apps and explicit task modules
try:
    # autodiscover tasks from INSTALLED_APPS (will attempt to import '<app>.tasks')
    app.autodiscover_tasks()
except Exception:
    # In case autodiscover is not available or fails for some reason, fall back
    # to explicit imports of known task modules so the worker registers them.
    pass

# Explicitly import application-specific task modules so tasks like
# 'app.tasks.tapis_storage.discover_and_create_flight_projects' are registered
try:
    import app.tasks.tapis_storage  # noqa: F401
except Exception:
    # Import failures should not prevent the worker from starting; log if needed
    pass
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