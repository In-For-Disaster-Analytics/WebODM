import ast
import json
import logging
from datetime import timedelta

import requests
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
import secrets
import string

logger = logging.getLogger('app.logger')


class TapisOAuth2Client(models.Model):
    """
    Model to store Tapis OAuth2 client configurations
    """
    client_id = models.CharField(max_length=255, unique=True)
    client_secret = models.CharField(max_length=255)
    tenant_id = models.CharField(max_length=100)
    base_url = models.URLField(help_text="Tapis base URL (e.g., https://tacc.tapis.io)")
    
    # OAuth2 configuration
    authorization_url = models.URLField(blank=True, help_text="OAuth2 authorization endpoint")
    token_url = models.URLField(blank=True, help_text="OAuth2 token endpoint")
    callback_url = models.URLField(help_text="OAuth2 callback URL for this WebODM instance")
    
    # Client metadata
    name = models.CharField(max_length=255, help_text="Descriptive name for this OAuth2 client")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_oauth2_clients')
    
    class Meta:
        verbose_name = "Tapis OAuth2 Client"
        verbose_name_plural = "Tapis OAuth2 Clients"
    
    def __str__(self):
        return f"{self.name} ({self.client_id})"
    
    def save(self, *args, **kwargs):
        # Auto-generate authorization and token URLs if not provided
        if not self.authorization_url:
            self.authorization_url = f"{self.base_url.rstrip('/')}/v3/oauth2/authorize"
        
        if not self.token_url:
            self.token_url = f"{self.base_url.rstrip('/')}/v3/oauth2/tokens"
            
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_client_secret(cls):
        """Generate a secure client secret"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))


class TapisOAuth2Token(models.Model):
    """
    Model to store OAuth2 tokens for users
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tapis_oauth2_tokens')
    client = models.ForeignKey(TapisOAuth2Client, on_delete=models.CASCADE)
    
    # OAuth2 tokens
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True)
    token_type = models.CharField(max_length=50, default='Bearer')
    
    # Token metadata
    scope = models.TextField(blank=True, help_text="Space-separated list of scopes")
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tapis OAuth2 Token"
        verbose_name_plural = "Tapis OAuth2 Tokens"
        unique_together = ['user', 'client']
    
    def __str__(self):
        return f"Token for {self.user.username} ({self.client.name})"
    
    @property
    def is_expired(self):
        """Check if the token is expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        """Check if the token is valid (exists and not expired)"""
        return bool(self.get_access_token_value()) and not self.is_expired

    @staticmethod
    def _extract_access_token(payload):
        """
        Recursively extract the raw JWT string from a payload.
        """
        if not payload:
            return None

        # If payload is already a JWT string, return as-is
        if isinstance(payload, str):
            stripped = payload.strip()
            if stripped.startswith('{') and stripped.endswith('}'):
                # Try to decode JSON or literal dict representation
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    try:
                        payload = ast.literal_eval(stripped)
                    except (SyntaxError, ValueError):
                        return stripped
                else:
                    return TapisOAuth2Token._extract_access_token(payload)
            else:
                return stripped

        if isinstance(payload, dict):
            # Common Tapis structures wrap the actual token in nested objects
            if 'access_token' in payload:
                return TapisOAuth2Token._extract_access_token(payload['access_token'])
            if 'result' in payload:
                return TapisOAuth2Token._extract_access_token(payload['result'])

        return None

    @classmethod
    def extract_access_token_value(cls, payload):
        """Public helper for extracting JWT strings from payloads."""
        return cls._extract_access_token(payload)

    def get_access_token_value(self):
        """
        Return the usable JWT string for this token, handling any stored payload structure.
        """
        value = self._extract_access_token(self.access_token)
        if value:
            return value
        # Fallback to raw value for backwards compatibility
        if isinstance(self.access_token, str):
            return self.access_token.strip()
        return None

    def refresh(self):
        """
        Refresh the access token using the stored refresh token.
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available for this Tapis token.")

        token_data = {
            'grant_type': 'refresh_token',
            'client_id': self.client.client_id,
            'client_secret': self.client.client_secret,
            'refresh_token': self.refresh_token
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Tapis-Tenant': self.client.tenant_id,
            'Accept': 'application/json'
        }

        try:
            response = requests.post(
                self.client.token_url,
                data=token_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error(f"Tapis token refresh failed: {exc}")
            raise

        try:
            refreshed = response.json()
        except ValueError as exc:
            logger.error(f"Tapis token refresh returned non-JSON response: {exc}")
            raise

        if isinstance(refreshed, dict) and refreshed.get('status') == 'success' and 'result' in refreshed:
            refreshed = refreshed['result']

        new_access_token = self._extract_access_token(refreshed.get('access_token'))
        if not new_access_token:
            logger.error("Tapis refresh response did not include a usable access token.")
            raise ValueError("No access token in Tapis refresh response.")

        expires_in = refreshed.get('expires_in')
        expires_at = None
        if expires_in:
            try:
                expires_at = timezone.now() + timedelta(seconds=int(expires_in))
            except (TypeError, ValueError):
                logger.warning("Invalid expires_in value in Tapis refresh response.")

        # Persist refreshed values
        self.access_token = new_access_token
        if refreshed.get('refresh_token'):
            self.refresh_token = refreshed['refresh_token']
        if refreshed.get('token_type'):
            self.token_type = refreshed['token_type']
        if refreshed.get('scope'):
            self.scope = refreshed['scope']
        self.expires_at = expires_at
        self.save()

        logger.info(f"Refreshed Tapis token for user {self.user.username}")
        return self.access_token

    def get_or_refresh_access_token(self):
        """
        Return a valid access token, refreshing when necessary.
        """
        access_token = self.get_access_token_value()
        if access_token and not self.is_expired:
            return access_token

        if access_token and not self.refresh_token:
            # Token string present but cannot refresh; return the stale token as last resort
            logger.warning("Tapis token is expired but no refresh token is available.")
            return access_token

        try:
            return self.refresh()
        except Exception as exc:
            logger.error(f"Unable to refresh Tapis token for {self.user.username}: {exc}")
            return access_token


class TapisOAuth2State(models.Model):
    """
    Model to store OAuth2 state parameters for CSRF protection
    """
    state = models.CharField(max_length=128, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    client = models.ForeignKey(TapisOAuth2Client, on_delete=models.CASCADE)
    
    # Additional parameters to restore after OAuth flow
    redirect_after_auth = models.URLField(blank=True, help_text="URL to redirect to after successful authentication")
    additional_data = models.TextField(default='{}', blank=True, help_text="Additional data to store during OAuth flow (JSON string)")
    
    # Expiry for cleanup
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Tapis OAuth2 State"
        verbose_name_plural = "Tapis OAuth2 States"
    
    def __str__(self):
        return f"OAuth2 State {self.state}"
    
    @property
    def is_expired(self):
        """Check if the state is expired"""
        return timezone.now() > self.expires_at
    
    def get_additional_data(self):
        """Get additional data as a Python dict"""
        import json
        try:
            return json.loads(self.additional_data) if self.additional_data else {}
        except json.JSONDecodeError:
            return {}
    
    def set_additional_data(self, data):
        """Set additional data from a Python dict"""
        import json
        self.additional_data = json.dumps(data) if data else '{}'
    
    @classmethod
    def generate_state(cls):
        """Generate a secure random state string"""
        return secrets.token_urlsafe(64)
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired state objects"""
        cls.objects.filter(expires_at__lt=timezone.now()).delete()
