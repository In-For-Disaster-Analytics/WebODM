from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from app.models import TapisOAuth2Client
import logging

logger = logging.getLogger('app.logger')


@never_cache
def tapis_login_view(request):
    """
    Custom login view for Tapis OAuth2 only authentication
    """
    # Check if there's a default Tapis client configured
    try:
        default_client = TapisOAuth2Client.objects.filter(is_active=True).first()
        if default_client:
            # If user is not authenticated and we have a default client, 
            # they can access the login page
            if not request.user.is_authenticated:
                return render(request, 'app/registration/login.html', {
                    'default_tapis_client_id': default_client.client_id
                })
            else:
                # User is already authenticated, redirect to dashboard
                return redirect('/dashboard/')
        else:
            # No Tapis clients configured
            return render(request, 'app/registration/login.html', {
                'error': _('No Tapis OAuth2 clients configured. Please contact your administrator.')
            })
    except Exception as e:
        logger.error(f"Error in tapis_login_view: {str(e)}")
        return render(request, 'app/registration/login.html', {
            'error': _('Configuration error. Please contact your administrator.')
        })


@csrf_exempt
def tapis_logout_view(request):
    """
    Custom logout view for Tapis authentication
    """
    if request.user.is_authenticated:
        username = request.user.username
        logout(request)
        messages.success(request, _('You have been logged out successfully.'))
        logger.info(f"User {username} logged out")
    
    return redirect('tapis_login')


def tapis_login_redirect(request):
    """
    Redirect to the first available Tapis OAuth2 client for login
    """
    try:
        default_client = TapisOAuth2Client.objects.filter(is_active=True).first()
        if default_client:
            redirect_after = request.GET.get('next', '/dashboard/')
            return redirect(f'/api/oauth2/tapis/authorize/{default_client.client_id}/?redirect_after={redirect_after}')
        else:
            messages.error(request, _('No Tapis OAuth2 clients configured.'))
            return redirect('tapis_login')
    except Exception as e:
        logger.error(f"Error in tapis_login_redirect: {str(e)}")
        messages.error(request, _('Authentication configuration error.'))
        return redirect('tapis_login')