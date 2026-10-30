from django.db import migrations, models
from django.db.models import Q
import django.contrib.postgres.fields.jsonb


class Migration(migrations.Migration):
    dependencies = [('app', '0058_splat_run')]
    operations = [
        migrations.AddField('splatrun', 'backend', models.CharField(default='direct_tapis', max_length=24)),
        migrations.AddField('splatrun', 'cluster_task_uuid', models.UUIDField(null=True, blank=True)),
        migrations.AddField('splatrun', 'backend_profile', models.CharField(default='', blank=True, max_length=100)),
        migrations.AddField('splatrun', 'phase', models.CharField(default='', blank=True, max_length=64)),
        migrations.AddField('splatrun', 'progress', django.contrib.postgres.fields.jsonb.JSONField(null=True, blank=True)),
        migrations.RemoveConstraint('splatrun', 'one_active_splat_run_per_task'),
        migrations.AlterField('splatrun', 'state', models.CharField(default='preparing', max_length=24, db_index=True,
            choices=[(s, s) for s in ('preparing', 'awaiting_signin', 'submitting', 'submission_unknown', 'queued', 'running',
                                      'result_ready', 'cancel_pending', 'importing', 'ready', 'failed', 'canceled')])),
        migrations.AddConstraint('splatrun', models.UniqueConstraint(fields=['task'],
            condition=Q(state__in=('preparing', 'awaiting_signin', 'submitting', 'submission_unknown', 'queued', 'running',
                                  'result_ready', 'cancel_pending', 'importing')), name='one_active_splat_run_per_task')),
    ]
