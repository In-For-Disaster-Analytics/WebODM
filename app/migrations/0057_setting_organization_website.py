from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0056_update_plugins'),
    ]

    operations = [
        migrations.AlterField(
            model_name='setting',
            name='organization_website',
            field=models.URLField(
                blank=True,
                default='https://github.com/WebODM/WebODM/',
                help_text='The website URL of your organization',
                max_length=255,
                null=True,
                verbose_name='Organization website',
            ),
        ),
    ]
