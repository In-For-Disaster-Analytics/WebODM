import uuid

from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import Q

from .task import Task


class SplatRun(models.Model):
    """
    One attempt to train a Gaussian splats model for a task on LS6 (OpenSplat via Tapis)
    """
    PREPARING = 'preparing'
    AWAITING_SIGNIN = 'awaiting_signin'
    SUBMITTING = 'submitting'
    SUBMISSION_UNKNOWN = 'submission_unknown'
    QUEUED = 'queued'
    RUNNING = 'running'
    IMPORTING = 'importing'
    READY = 'ready'
    FAILED = 'failed'
    CANCELED = 'canceled'

    ACTIVE_STATES = (PREPARING, AWAITING_SIGNIN, SUBMITTING, SUBMISSION_UNKNOWN, QUEUED, RUNNING, IMPORTING)
    STATE_CHOICES = tuple((s, s) for s in ACTIVE_STATES + (READY, FAILED, CANCELED))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='splat_runs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='splat_runs',
                             help_text="The user who submitted the run; only they can sync or cancel it")
    state = models.CharField(max_length=24, choices=STATE_CHOICES, default=PREPARING, db_index=True)
    tapis_job_uuid = models.CharField(max_length=64, blank=True, default='')
    settings = JSONField(default=dict, blank=True)
    snapshot_path = models.CharField(max_length=1024, blank=True, default='')
    output_path = models.CharField(max_length=1024, blank=True, default='')
    conversion_celery_id = models.CharField(max_length=64, blank=True, default='')
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', )
        constraints = [
            # At most one active run per task, enforced by the database
            models.UniqueConstraint(fields=['task'], condition=Q(state__in=('preparing', 'awaiting_signin', 'submitting', 'submission_unknown', 'queued', 'running', 'importing')),
                                    name='one_active_splat_run_per_task'),
        ]

    @property
    def is_active(self):
        return self.state in self.ACTIVE_STATES

    def __str__(self):
        return "SplatRun {} ({})".format(self.id, self.state)
