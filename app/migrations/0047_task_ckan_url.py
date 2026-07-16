from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0046_auto_20250910_1902'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='ckan_url',
            field=models.URLField(
                blank=True,
                null=True,
                help_text='CKAN dataset URL if this task has been published',
                verbose_name='CKAN URL',
            ),
        ),
    ]
