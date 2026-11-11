from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('app', '0061_task_versions'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='submitted_by',
            field=models.ForeignKey(blank=True, help_text='User who last started or restarted this task. Their Tapis identity is used for all processing node calls. Falls back to the project owner when empty.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='submitted_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Submitted by'),
        ),
    ]
