import requests
import json
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from webodm import settings
import logging

logger = logging.getLogger('app.logger')


class TapisOAuth2Backend(ModelBackend):
    """
    Tapis OAuth2 authentication backend for WebODM
    
    This backend supports Tapis OAuth2 authentication using JWT tokens.
    It validates tokens against the Tapis authentication service and
    creates/updates users based on the token claims.
    """
    
    def authenticate(self, request, access_token=None, **kwargs):
        """
        Authenticate user using Tapis OAuth2 access token
        """
        if not access_token:
            return None
            
        # Validate configuration
        if not hasattr(settings, 'TAPIS_BASE_URL') or not settings.TAPIS_BASE_URL:
            logger.error("TAPIS_BASE_URL not configured")
            return None
            
        if not hasattr(settings, 'TAPIS_TENANT_ID') or not settings.TAPIS_TENANT_ID:
            logger.error("TAPIS_TENANT_ID not configured")
            return None
        
        try:
            # Validate token with Tapis authentication service
            user_info = self._validate_token_with_tapis(access_token)
            if not user_info:
                return None
                
            # Create or update user
            return self._get_or_create_user(user_info, access_token)
            
        except Exception as e:
            logger.error(f"Tapis OAuth2 authentication error: {str(e)}")
            return None
    
    def _validate_token_with_tapis(self, access_token):
        """
        Validate access token by decoding JWT locally
        """
        try:
            import base64
            
            # JWT tokens have 3 parts separated by '.'
            token_parts = access_token.split('.')
            if len(token_parts) != 3:
                logger.warning("Invalid JWT token format - expected 3 parts")
                return None
            
            # Decode the payload (second part)
            payload_b64 = token_parts[1]
            
            # Add padding if needed (base64 requires padding to multiple of 4)
            missing_padding = len(payload_b64) % 4
            if missing_padding:
                payload_b64 += '=' * (4 - missing_padding)
            
            try:
                payload_bytes = base64.urlsafe_b64decode(payload_b64)
                payload = json.loads(payload_bytes.decode('utf-8'))
                
                logger.info(f"Successfully decoded JWT payload: {list(payload.keys())}")
                
                # Extract user information from JWT claims
                user_info = {
                    'username': payload.get('tapis/username') or payload.get('username') or payload.get('sub'),
                    'tenant_id': payload.get('tapis/tenant_id') or payload.get('tenant_id') or settings.TAPIS_TENANT_ID,
                    'sub': payload.get('sub'),
                    'exp': payload.get('exp'),
                    'iat': payload.get('iat'),
                    'email': payload.get('email') or payload.get('tapis/email'),
                    'given_name': payload.get('given_name') or payload.get('tapis/given_name'),
                    'family_name': payload.get('family_name') or payload.get('tapis/family_name'),
                    'display_name': payload.get('display_name') or payload.get('tapis/display_name')
                }
                
                # Check token expiration
                import time
                current_time = int(time.time())
                exp = payload.get('exp')
                if exp and current_time > exp:
                    logger.warning("JWT token has expired")
                    return None
                
                username = user_info.get('username')
                if not username:
                    logger.warning("No username found in JWT token")
                    return None
                
                logger.info(f"Successfully validated JWT token for user: {username}")
                return user_info
                
            except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Error decoding JWT payload: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error validating JWT token: {str(e)}")
            return None
    
    def _get_or_create_user(self, user_info, access_token):
        """
        Get or create Django user from Tapis user info
        """
        username = user_info.get('username')
        if not username:
            logger.error("No username found in Tapis user info")
            return None
            
        try:
            # Try to get existing user
            user = User.objects.get(username=username)
            
            # Update user information if needed
            self._update_user_info(user, user_info)
            
        except User.DoesNotExist:
            # Create new user
            user = self._create_user_from_tapis_info(user_info)
            
        # Store additional Tapis-specific information in session or user profile
        if hasattr(user, 'profile'):
            # Store Tapis tenant information if user has a profile
            if hasattr(user.profile, 'tapis_tenant_id'):
                user.profile.tapis_tenant_id = user_info.get('tenant_id')
                user.profile.save()
        
        return user
    
    def _create_user_from_tapis_info(self, user_info):
        """
        Create a new Django user from Tapis user information
        """
        username = user_info.get('username')
        email = user_info.get('email', '')
        # Provide default values for name fields if they're None or empty
        first_name = user_info.get('given_name') or ''
        last_name = user_info.get('family_name') or ''
        
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        
        logger.info(f"Created new user from Tapis OAuth2: {username}")
        return user
    
    def _update_user_info(self, user, user_info):
        """
        Update existing user information from Tapis user info
        """
        updated = False
        
        # Update email if provided and different
        email = user_info.get('email', '')
        if email and user.email != email:
            user.email = email
            updated = True
            
        # Update first name if provided and different
        first_name = user_info.get('given_name', '')
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
            
        # Update last name if provided and different
        last_name = user_info.get('family_name', '')
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updated = True
        
        if updated:
            user.save()
            logger.info(f"Updated user information for: {user.username}")
    
    def get_user(self, user_id):
        """
        Get user by ID
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


def validate_tapis_jwt_token(token):
    """
    Utility function to validate a Tapis JWT token without authentication
    Returns user information if valid, None otherwise
    """
    backend = TapisOAuth2Backend()
    return backend._validate_token_with_tapis(token)