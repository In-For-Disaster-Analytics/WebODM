import json
import requests
from datetime import timedelta
from urllib.parse import urlencode, parse_qs, urlparse

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models import TapisOAuth2Client, TapisOAuth2Token, TapisOAuth2State
from app.auth.tapis_oauth2 import TapisOAuth2Backend
from webodm import settings

import logging

logger = logging.getLogger('app.logger')


class TapisOAuth2AuthorizeView(View):
    """
    Initiate Tapis OAuth2 authorization flow
    """
    
    def get(self, request, client_id):
        try:
            client = get_object_or_404(TapisOAuth2Client, client_id=client_id, is_active=True)
            
            # Generate and store state for CSRF protection
            state = TapisOAuth2State.generate_state()
            redirect_after = request.GET.get('redirect_after', '/dashboard/')
            
            # Create state object with 10 minute expiry
            state_obj = TapisOAuth2State.objects.create(
                state=state,
                user=request.user if request.user.is_authenticated else None,
                client=client,
                redirect_after_auth=redirect_after,
                expires_at=timezone.now() + timedelta(minutes=10)
            )
            
            # Build authorization URL
            auth_params = {
                'client_id': client.client_id,
                'response_type': 'code',
                'redirect_uri': client.callback_url,
                'state': state,
                'scope': 'openid profile'  # Basic scopes
            }
            
            auth_url = f"{client.authorization_url}?{urlencode(auth_params)}"
            
            logger.info(f"Redirecting to Tapis OAuth2 authorization: {client.name}")
            return HttpResponseRedirect(auth_url)
            
        except Exception as e:
            logger.error(f"Error initiating Tapis OAuth2 flow: {str(e)}")
            return JsonResponse({'error': 'Failed to initiate OAuth2 flow'}, status=500)


class TapisOAuth2CallbackView(View):
    """
    Handle OAuth2 callback from Tapis
    """
    
    def get(self, request):
        try:
            # Extract parameters
            code = request.GET.get('code')
            state = request.GET.get('state')
            error = request.GET.get('error')
            error_description = request.GET.get('error_description')
            
            # Handle OAuth2 errors
            if error:
                logger.error(f"OAuth2 error: {error} - {error_description}")
                return JsonResponse({
                    'error': f'OAuth2 error: {error}',
                    'description': error_description
                }, status=400)
            
            if not code or not state:
                return JsonResponse({'error': 'Missing code or state parameter'}, status=400)
            
            # Validate state
            try:
                state_obj = TapisOAuth2State.objects.get(state=state)
                if state_obj.is_expired:
                    state_obj.delete()
                    return JsonResponse({'error': 'OAuth2 state expired'}, status=400)
                    
                client = state_obj.client
            except TapisOAuth2State.DoesNotExist:
                return JsonResponse({'error': 'Invalid OAuth2 state'}, status=400)
            
            # Exchange code for tokens
            token_data = self._exchange_code_for_tokens(client, code)
            if not token_data:
                logger.error("Token exchange returned None")
                return JsonResponse({'error': 'Failed to exchange code for tokens'}, status=500)
            
            logger.info(f"Token data keys: {list(token_data.keys()) if token_data else 'None'}")
            
            # Check if access_token exists in response
            if 'access_token' not in token_data:
                logger.error(f"No access_token in response. Available keys: {list(token_data.keys())}")
                return JsonResponse({'error': 'No access token in Tapis response'}, status=500)
            
            # Extract the actual JWT token from nested structure
            access_token_data = token_data['access_token']
            if isinstance(access_token_data, dict) and 'access_token' in access_token_data:
                jwt_token = access_token_data['access_token']
            elif isinstance(access_token_data, str):
                jwt_token = access_token_data
            else:
                logger.error(f"Invalid access_token structure: {type(access_token_data)}")
                return JsonResponse({'error': 'Invalid access token structure in Tapis response'}, status=500)
            
            logger.info(f"Extracted JWT token string: {jwt_token[:50]}...")
            
            # Authenticate user with access token
            backend = TapisOAuth2Backend()
            user = backend.authenticate(request, access_token=jwt_token)
            
            if not user:
                return JsonResponse({'error': 'Failed to authenticate user with Tapis'}, status=401)
            
            # Log the user in
            login(request, user, backend='app.auth.tapis_oauth2.TapisOAuth2Backend')
            
            # Store tokens
            self._store_user_tokens(user, client, token_data)
            
            # Trigger flight discovery in background after successful login
            self._trigger_flight_discovery(user, client)
            
            # Cleanup state
            redirect_url = state_obj.redirect_after_auth or '/dashboard/'
            state_obj.delete()
            
            logger.info(f"Successfully authenticated user {user.username} with Tapis OAuth2")
            
            return HttpResponseRedirect(redirect_url)
            
        except KeyError as e:
            logger.error(f"KeyError in OAuth2 callback: {str(e)} - Missing key in response")
            return JsonResponse({'error': f'Missing key in OAuth2 response: {str(e)}'}, status=500)
        except Exception as e:
            logger.error(f"Error in OAuth2 callback: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return JsonResponse({'error': 'OAuth2 callback failed'}, status=500)
    
    def _exchange_code_for_tokens(self, client, code):
        """
        Exchange authorization code for access and refresh tokens
        """
        try:
            token_data = {
                'grant_type': 'authorization_code',
                'client_id': client.client_id,
                'client_secret': client.client_secret,
                'code': code,
                'redirect_uri': client.callback_url
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Tapis-Tenant': client.tenant_id,
                'Accept': 'application/json'
            }
            
            response = requests.post(client.token_url, data=token_data, headers=headers)
            
            if response.status_code == 200:
                token_response = response.json()
                logger.info(f"Tapis token response: {token_response}")
                
                # Tapis API wraps the actual token data in a 'result' field
                if token_response.get('status') == 'success' and 'result' in token_response:
                    return token_response['result']
                else:
                    logger.error(f"Tapis API error: {token_response.get('message', 'Unknown error')}")
                    return None
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {str(e)}")
            return None
    
    def _store_user_tokens(self, user, client, token_data):
        """
        Store OAuth2 tokens for the user
        """
        try:
            # Calculate expiration time
            expires_in = token_data.get('expires_in')
            expires_at = None
            if expires_in:
                expires_at = timezone.now() + timedelta(seconds=int(expires_in))
            
            # Create or update token
            token, created = TapisOAuth2Token.objects.update_or_create(
                user=user,
                client=client,
                defaults={
                    'access_token': token_data.get('access_token'),
                    'refresh_token': token_data.get('refresh_token', ''),
                    'token_type': token_data.get('token_type', 'Bearer'),
                    'scope': token_data.get('scope', ''),
                    'expires_at': expires_at
                }
            )
            
            logger.info(f"{'Created' if created else 'Updated'} OAuth2 token for user {user.username}")
            
        except Exception as e:
            logger.error(f"Error storing user tokens: {str(e)}")
    
    def _trigger_flight_discovery(self, user, client):
        """
        Trigger background flight discovery after successful Tapis authentication
        """
        try:
            from app.models.tapis_preferences import TapisUserPreferences
            
            # Check user preferences
            preferences = TapisUserPreferences.get_or_create_for_user(user)
            
            if not preferences.should_run_auto_discovery():
                logger.info(f"Skipping auto-discovery for user {user.username} due to preferences or cooldown")
                return
            
            logger.info(f"Starting auto-discovery for user {user.username}")
            
            try:
                from app.tasks.tapis_storage import discover_and_create_flight_projects
                
                # Trigger discovery as background task
                result = discover_and_create_flight_projects.delay(
                    user_id=user.id,
                    client_id=client.client_id
                )
                
                logger.info(f"Triggered flight discovery task {result.id} for user {user.username}")
                
                # Update last discovery timestamp
                preferences.update_last_discovery()
                
            except ImportError:
                # Fallback to synchronous discovery if Celery is not available
                logger.warning("Celery not available, running synchronous flight discovery")
                try:
                    from app.services.tapis_storage import TapisFlightDiscoveryService
                    
                    results = TapisFlightDiscoveryService.discover_and_create_projects(user, client)
                    logger.info(f"Synchronous flight discovery completed: {results['projects_created']} projects created")
                    
                    # Update last discovery timestamp
                    preferences.update_last_discovery()
                    
                except Exception as e:
                    logger.error(f"Failed to run synchronous flight discovery: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to trigger flight discovery: {e}")


class TapisOAuth2TokenRefreshView(APIView):
    """
    Refresh OAuth2 access token using refresh token
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, client_id):
        try:
            client = get_object_or_404(TapisOAuth2Client, client_id=client_id, is_active=True)
            
            try:
                token_obj = TapisOAuth2Token.objects.get(user=request.user, client=client)
            except TapisOAuth2Token.DoesNotExist:
                return Response({'error': 'No token found for this client'}, status=404)
            
            if not token_obj.refresh_token:
                return Response({'error': 'No refresh token available'}, status=400)
            
            # Refresh the token
            new_token_data = self._refresh_access_token(client, token_obj.refresh_token)
            
            if not new_token_data:
                return Response({'error': 'Failed to refresh token'}, status=500)
            
            # Update stored token
            expires_in = new_token_data.get('expires_in')
            expires_at = None
            if expires_in:
                expires_at = timezone.now() + timedelta(seconds=int(expires_in))
            
            token_obj.access_token = new_token_data.get('access_token')
            token_obj.token_type = new_token_data.get('token_type', 'Bearer')
            token_obj.expires_at = expires_at
            
            # Update refresh token if provided
            if 'refresh_token' in new_token_data:
                token_obj.refresh_token = new_token_data['refresh_token']
            
            token_obj.save()
            
            return Response({
                'message': 'Token refreshed successfully',
                'expires_at': expires_at.isoformat() if expires_at else None
            })
            
        except Exception as e:
            logger.error(f"Error refreshing OAuth2 token: {str(e)}")
            return Response({'error': 'Failed to refresh token'}, status=500)
    
    def _refresh_access_token(self, client, refresh_token):
        """
        Refresh access token using refresh token
        """
        try:
            token_data = {
                'grant_type': 'refresh_token',
                'client_id': client.client_id,
                'client_secret': client.client_secret,
                'refresh_token': refresh_token
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Tapis-Tenant': client.tenant_id,
                'Accept': 'application/json'
            }
            
            response = requests.post(client.token_url, data=token_data, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing access token: {str(e)}")
            return None


class TapisOAuth2StatusView(APIView):
    """
    Get OAuth2 status for authenticated user
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            tokens = TapisOAuth2Token.objects.filter(user=request.user).select_related('client')
            
            token_info = []
            for token in tokens:
                token_info.append({
                    'client_id': token.client.client_id,
                    'client_name': token.client.name,
                    'tenant_id': token.client.tenant_id,
                    'is_valid': token.is_valid,
                    'expires_at': token.expires_at.isoformat() if token.expires_at else None,
                    'scope': token.scope
                })
            
            return Response({
                'user': request.user.username,
                'tokens': token_info
            })
            
        except Exception as e:
            logger.error(f"Error getting OAuth2 status: {str(e)}")
            return Response({'error': 'Failed to get OAuth2 status'}, status=500)


class TapisOAuth2RevokeView(APIView):
    """
    Revoke OAuth2 tokens for a client
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, client_id):
        try:
            client = get_object_or_404(TapisOAuth2Client, client_id=client_id, is_active=True)
            
            try:
                token_obj = TapisOAuth2Token.objects.get(user=request.user, client=client)
            except TapisOAuth2Token.DoesNotExist:
                return Response({'error': 'No token found for this client'}, status=404)
            
            # Optional: Try to revoke token with Tapis (if endpoint is available)
            # This is optional as not all OAuth2 providers support token revocation
            
            # Delete local token
            token_obj.delete()
            
            logger.info(f"Revoked OAuth2 token for user {request.user.username} and client {client.name}")
            
            return Response({'message': 'Token revoked successfully'})
            
        except Exception as e:
            logger.error(f"Error revoking OAuth2 token: {str(e)}")
            return Response({'error': 'Failed to revoke token'}, status=500)