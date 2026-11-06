import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from app.models import Task, TaskRun
from app.models.task_run import TERMINAL_STATUSES


class Command(BaseCommand):
    help = "Create run records for terminal tasks that do not have one yet"

    def handle(self, **options):
        created = skipped = 0

        tasks = Task.objects.filter(status__in=TERMINAL_STATUSES).exclude(runs__isnull=False)
        for task in tasks.iterator():
            run = TaskRun.record_from(task, finished_at=self.last_modified(task))
            if run is None:
                skipped += 1
            else:
                created += 1

        self.stdout.write("Created: {}".format(created))
        self.stdout.write("Skipped: {}".format(skipped))

    @staticmethod
    def last_modified(task):
        """Best available approximation of when the task finished"""
        for path in (task.assets_path("log.json"), task.assets_path(), task.task_path()):
            try:
                return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
            except OSError:
                continue
        return None
