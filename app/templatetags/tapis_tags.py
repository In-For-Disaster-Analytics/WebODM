from django import template
from django.utils import timezone
from app.models.oauth2 import TapisOAuth2Token

register = template.Library()

@register.simple_tag
def get_user_tapis_token(user):
    """
    Get the current user's latest Tapis OAuth2 token if it exists.

    Expired token metadata is still returned so loaded pages can redirect the
    user through the logout flow immediately after the JWT lifetime ends.
    """
    if not user.is_authenticated:
        return None
    
    token = TapisOAuth2Token.objects.filter(user=user).order_by('-updated_at').first()
    if token and not token.expires_at:
        token._get_effective_expiration()
        if not token.expires_at:
            token.expires_at = timezone.now()
    
    return token

@register.filter
def timeuntil_seconds(value):
    """
    Calculate seconds until a given datetime
    """
    if not value:
        return 0
    
    now = timezone.now()
    if value > now:
        delta = value - now
        return int(delta.total_seconds())
    
    return 0
