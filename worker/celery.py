
"""
Minimal Celery module for worker compatibility.

This file intentionally keeps a tiny surface area: it imports the
pre-configured Celery `app` (and `MockAsyncResult`) from the
`worker` package (`worker/__init__.py`) where the actual setup runs.
Keeping this module simple avoids circular import and indentation issues.
"""

from worker import app, MockAsyncResult

__all__ = ["app", "MockAsyncResult"]

if __name__ == "__main__":
    app.start()