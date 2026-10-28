import uuid

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('app', '0057_setting_organization_website'),
    ]

    operations = [
        migrations.CreateModel(
            name='SplatRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('state', models.CharField(choices=[('preparing', 'preparing'), ('awaiting_signin', 'awaiting_signin'), ('submitting', 'submitting'), ('submission_unknown', 'submission_unknown'), ('queued', 'queued'), ('running', 'running'), ('importing', 'importing'), ('ready', 'ready'), ('failed', 'failed'), ('canceled', 'canceled')], db_index=True, default='preparing', max_length=24)),
                ('tapis_job_uuid', models.CharField(blank=True, default='', max_length=64)),
                ('settings', django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=dict)),
                ('snapshot_path', models.CharField(blank=True, default='', max_length=1024)),
                ('output_path', models.CharField(blank=True, default='', max_length=1024)),
                ('conversion_celery_id', models.CharField(blank=True, default='', max_length=64)),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='splat_runs', to='app.Task')),
                ('user', models.ForeignKey(help_text='The user who submitted the run; only they can sync or cancel it', on_delete=django.db.models.deletion.CASCADE, related_name='splat_runs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='splatrun',
            constraint=models.UniqueConstraint(condition=Q(state__in=('preparing', 'awaiting_signin', 'submitting', 'submission_unknown', 'queued', 'running', 'importing')), fields=('task',), name='one_active_splat_run_per_task'),
        ),
    ]
