
# Import Django and configure it first

"""
Celery worker application module.
This module now just imports the app instance from worker/__init__.py
where the actual Celery setup happens.
"""
from worker import app, MockAsyncResult  # This imports the pre-configured app from __init__.py

# For backward compatibility
__all__ = ['app', 'MockAsyncResult']

# Result backend configuration
app.conf.result_backend_transport_options = {
    'retry_policy': {
        'timeout': 5.0
    }
}

if __name__ == '__main__':
    app.start()
from worker import app  # This imports the pre-configured app from __init__.py

# Keep these for compatibility with existing code
__all__ = ['app', 'MockAsyncResult']
from worker import MockAsyncResult

# No configuration here - it's all in __init__.py

# For reference, the old configuration was:
app.conf.result_backend_transport_options = {
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
        'options': {
        	'expires': 1799,
    },
}

# Mock class for handling async results during testing
class MockAsyncResult:
    def __init__(self, celery_task_id, result = None):
        from worker import app, MockAsyncResult  # This imports the pre-configured app from __init__.py
        self.celery_task_id = celery_task_id
        self.state = "PENDING"

        if result is None:
            if celery_task_id == 'bogus':
                self.result = None
            else:
        app.conf.result_backend_transport_options = { 
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