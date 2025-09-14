from django import template
from django.utils import timezone
from app.models.oauth2 import TapisOAuth2Token

register = template.Library()

@register.simple_tag
def get_user_tapis_token(user):
    """
    Get the current user's Tapis OAuth2 token if it exists and is valid
    """
    if not user.is_authenticated:
        return None
    
    try:
        token = TapisOAuth2Token.objects.filter(user=user).first()
        if token and not token.is_expired:
            return token
    except TapisOAuth2Token.DoesNotExist:
        pass
    
    return None

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