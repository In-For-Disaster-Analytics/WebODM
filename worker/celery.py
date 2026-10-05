
"""
Minimal Celery module for worker compatibility.

This file intentionally keeps a tiny surface area: it imports the
pre-configured Celery `app` (and `MockAsyncResult`) from the
`worker` package (`worker/__init__.py`) where the actual setup runs.
Keeping this module simple avoids circular import and indentation issues.
"""

from worker import app, MockAsyncResult

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
    'cleanup-cache-directory': {
        'task': 'worker.tasks.cleanup_cache_directory',
        'schedule': 21600,
        'options': {
            'expires': 10799,
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

__all__ = ["app", "MockAsyncResult"]

if __name__ == "__main__":
    app.start()
