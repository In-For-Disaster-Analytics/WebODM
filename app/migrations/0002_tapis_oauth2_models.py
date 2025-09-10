# Generated manually for Tapis OAuth2 integration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TapisOAuth2Client',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_id', models.CharField(max_length=255, unique=True)),
                ('client_secret', models.CharField(max_length=255)),
                ('tenant_id', models.CharField(max_length=100)),
                ('base_url', models.URLField(help_text='Tapis base URL (e.g., https://tacc.tapis.io)')),
                ('authorization_url', models.URLField(blank=True, help_text='OAuth2 authorization endpoint')),
                ('token_url', models.URLField(blank=True, help_text='OAuth2 token endpoint')),
                ('callback_url', models.URLField(help_text='OAuth2 callback URL for this WebODM instance')),
                ('name', models.CharField(help_text='Descriptive name for this OAuth2 client', max_length=255)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_oauth2_clients', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tapis OAuth2 Client',
                'verbose_name_plural': 'Tapis OAuth2 Clients',
            },
        ),
        migrations.CreateModel(
            name='TapisOAuth2Token',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_token', models.TextField()),
                ('refresh_token', models.TextField(blank=True)),
                ('token_type', models.CharField(default='Bearer', max_length=50)),
                ('scope', models.TextField(blank=True, help_text='Space-separated list of scopes')),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.tapisoauth2client')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tapis_oauth2_tokens', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tapis OAuth2 Token',
                'verbose_name_plural': 'Tapis OAuth2 Tokens',
            },
        ),
        migrations.CreateModel(
            name='TapisOAuth2State',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(max_length=128, unique=True)),
                ('redirect_after_auth', models.URLField(blank=True, help_text='URL to redirect to after successful authentication')),
                ('additional_data', models.TextField(blank=True, default="{}", help_text='Additional data to store during OAuth flow')),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.tapisoauth2client')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Tapis OAuth2 State',
                'verbose_name_plural': 'Tapis OAuth2 States',
            },
        ),
        migrations.AddConstraint(
            model_name='tapisoauth2token',
            constraint=models.UniqueConstraint(fields=('user', 'client'), name='unique_user_client_token'),
        ),
    ]