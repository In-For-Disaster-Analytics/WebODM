import json
import logging
import os
from datetime import datetime, timedelta

from PIL import Image
from django.contrib.postgres import fields
from django.db import models
from django.utils import timezone

from nodeodm import status_codes

logger = logging.getLogger('app.logger')

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')
TERMINAL_STATUSES = [status_codes.COMPLETED, status_codes.FAILED, status_codes.CANCELED]
DUPLICATE_WINDOW_SECONDS = 60


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    return None


def _as_str(value):
    return None if value is None else str(value)


class TaskRun(models.Model):
    """
    One row per terminal status change of a task. Survives task deletion.
    """
    STATUS_CHOICES = (
        (status_codes.COMPLETED, 'COMPLETED'),
        (status_codes.FAILED, 'FAILED'),
        (status_codes.CANCELED, 'CANCELED'),
    )

    task = models.ForeignKey('app.Task', null=True, blank=True, on_delete=models.SET_NULL, related_name='runs')
    task_name = models.CharField(max_length=255, blank=True, default="")
    project_id = models.IntegerField(null=True, blank=True)
    # Provenance keys that outlive the task row: the processing node's task id, and the
    # Tapis job that ran it (from ClusterODX's /task/<uuid>/tapis), from which queue wait,
    # wall time, exit status and charges can be pulled from Tapis later.
    task_uuid = models.CharField(max_length=255, blank=True, default="", db_index=True)
    tapis_job_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    tapis_job_name = models.CharField(max_length=255, null=True, blank=True)

    status = models.IntegerField(choices=STATUS_CHOICES, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(db_index=True)

    images_count = models.IntegerField(null=True, blank=True)
    resize_to = models.IntegerField(null=True, blank=True)
    image_width = models.IntegerField(null=True, blank=True)
    image_height = models.IntegerField(null=True, blank=True)

    processing_node = models.CharField(max_length=255, null=True, blank=True)
    engine = models.CharField(max_length=255, null=True, blank=True)
    engine_version = models.CharField(max_length=32, null=True, blank=True)

    options = fields.JSONField(default=list, blank=True)
    pc_quality = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    feature_quality = models.CharField(max_length=32, null=True, blank=True)
    fast_orthophoto = models.NullBooleanField(null=True, blank=True)
    split = models.IntegerField(null=True, blank=True)
    queue = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    nodes = models.IntegerField(null=True, blank=True)
    requested_minutes = models.IntegerField(null=True, blank=True)
    allocation = models.CharField(max_length=100, null=True, blank=True)
    rerun_from = models.CharField(max_length=64, null=True, blank=True)

    processing_time_ms = models.BigIntegerField(null=True, blank=True)
    odm_total_seconds = models.FloatField(null=True, blank=True)
    stage_seconds = fields.JSONField(null=True, blank=True)

    last_error = models.CharField(max_length=300, blank=True, default="")
    record_version = models.IntegerField(default=1)

    class Meta:
        ordering = ['-finished_at', '-id']

    def __str__(self):
        return "{} ({})".format(self.task_name, self.get_status_display())

    @classmethod
    def record_from(cls, task, finished_at=None, tapis_job=None):
        """
        Record the terminal state of a task. `tapis_job` is the optional JSON answer of
        the node's /task/<uuid>/tapis route ({tapisJobId, jobName, ...}). Never raises:
        failures are logged so that task processing is not interrupted. Returns the new
        row or None.
        """
        try:
            return cls._record_from(task, finished_at, tapis_job)
        except Exception as e:
            logger.warning("Cannot record run for task {}: {}".format(getattr(task, 'id', None), str(e)))
            return None

    @classmethod
    def _record_from(cls, task, finished_at, tapis_job=None):
        if task.status not in TERMINAL_STATUSES:
            return None

        finished_at = finished_at or timezone.now()
        # -1 (and 0) mean "unknown" on the task; store null so averages are not skewed.
        processing_time = task.processing_time if task.processing_time and task.processing_time > 0 else None
        started_at = finished_at - timedelta(milliseconds=processing_time) if processing_time else None

        # The same terminal state reported twice within a minute is one run, not two.
        # A later row with identical status and time (e.g. a restart that fails again
        # before reporting any processing time) is a new run and is kept.
        last = cls.objects.filter(task=task).order_by('-finished_at', '-id').first()
        if (last is not None and last.status == task.status and last.processing_time_ms == processing_time
                and abs((finished_at - last.finished_at).total_seconds()) < DUPLICATE_WINDOW_SECONDS):
            return None

        opts = {}
        for o in (task.options or []):
            if isinstance(o, dict) and 'name' in o:
                opts[o['name']] = o.get('value')

        node = task.processing_node
        job = tapis_job if isinstance(tapis_job, dict) else {}
        row = cls(
            task=task,
            task_name=task.name or "",
            project_id=task.project_id,
            task_uuid=task.uuid or "",
            tapis_job_id=_as_str(job.get('tapisJobId')),
            tapis_job_name=_as_str(job.get('jobName')),
            status=task.status,
            started_at=started_at,
            finished_at=finished_at,
            images_count=task.images_count,
            resize_to=task.resize_to,
            processing_node=(node.label or str(node)) if node else None,
            engine=node.engine if node else None,
            engine_version=node.engine_version if node else None,
            options=task.options or [],
            pc_quality=_as_str(opts.get('pc-quality')),
            feature_quality=_as_str(opts.get('feature-quality')),
            fast_orthophoto=_as_bool(opts.get('fast-orthophoto')),
            split=_as_int(opts.get('split')),
            queue=_as_str(opts.get('tapis-queue')),
            nodes=_as_int(opts.get('tapis-node')),
            requested_minutes=_as_int(opts.get('tapis-max-run-time')),
            allocation=_as_str(opts.get('tapis-allocation')),
            rerun_from=_as_str(opts.get('rerun-from')),
            processing_time_ms=processing_time,
            last_error=(task.last_error or "")[:300],
        )
        row.image_width, row.image_height = cls._first_image_size(task)

        if task.status == status_codes.COMPLETED:
            row.odm_total_seconds, row.stage_seconds = cls._parse_log(task.assets_path("log.json"))

        row.save()
        return row

    @staticmethod
    def _first_image_size(task):
        try:
            for name in sorted(task.scan_images()):
                if name.lower().endswith(IMAGE_EXTENSIONS):
                    with Image.open(task.get_image_path(name)) as im:
                        return im.size
        except Exception:
            pass
        return None, None

    @staticmethod
    def _parse_log(path):
        """
        Returns (total_seconds, {stage: seconds}) from ODM's log.json, or (None, None).
        """
        try:
            with open(path) as f:
                log = json.load(f)

            total = float(log['totalTime'])
            stages = log['stages']
            parse = lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))
            start = lambda s: parse(s['startTime'])
            end = parse(log['endTime']) if log.get('endTime') else start(stages[0]) + timedelta(seconds=total)

            seconds = {}
            for i, stage in enumerate(stages):
                stage_end = start(stages[i + 1]) if i + 1 < len(stages) else end
                seconds[stage['name']] = round((stage_end - start(stage)).total_seconds(), 3)
            return total, seconds
        except Exception:
            return None, None
