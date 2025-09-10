from django.conf import settings as django_settings
from app.models import TapisOAuth2Client


def tapis_oauth2_context(request):
    """
    Template context processor for Tapis OAuth2 integration
    Provides default client ID and configuration to templates
    """
    context = {
        'tapis_base_url': getattr(django_settings, 'TAPIS_BASE_URL', ''),
        'tapis_tenant_id': getattr(django_settings, 'TAPIS_TENANT_ID', ''),
        'default_tapis_client_id': None,
        'tapis_configured': False,
    }
    
    try:
        # Get the first active Tapis OAuth2 client as default
        default_client = TapisOAuth2Client.objects.filter(is_active=True).first()
        if default_client:
            context['default_tapis_client_id'] = default_client.client_id
            context['tapis_configured'] = True
    except Exception:
        # Database might not be migrated yet, or other issues
        pass
    
    return context