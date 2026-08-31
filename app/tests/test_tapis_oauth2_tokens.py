import base64
import json
import time

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.api.tapis_oauth2 import TapisOAuth2CallbackView
from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
from .classes import BootTestCase


def _b64url(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _make_jwt(exp_seconds=3600):
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
    exp = int(time.time()) + exp_seconds
    payload = _b64url(json.dumps({"exp": exp, "tapis/username": "testuser"}).encode("utf-8"))
    return f"{header}.{payload}.signature"


class TestTapisOAuth2TokenExpiry(BootTestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.get(username="testuser")
        self.oauth_client = TapisOAuth2Client.objects.create(
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant",
            base_url="https://tacc.tapis.io",
            callback_url="https://webodm.example.com/api/oauth2/tapis/callback",
            name="Test Client",
            description="Test Client",
        )

    def test_get_valid_access_token_returns_future_jwt(self):
        token_value = _make_jwt()
        token = TapisOAuth2Token.objects.create(
            user=self.user,
            client=self.oauth_client,
            access_token=token_value,
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )

        self.assertEqual(token.get_valid_access_token(), token_value)
        self.assertTrue(token.is_valid)

    def test_get_valid_access_token_rejects_expired_jwt_even_with_refresh_token(self):
        token = TapisOAuth2Token.objects.create(
            user=self.user,
            client=self.oauth_client,
            access_token=_make_jwt(exp_seconds=-60),
            refresh_token="legacy-refresh-token",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )

        self.assertIsNone(token.get_valid_access_token())
        self.assertFalse(token.is_valid)
        self.assertTrue(token.is_expired)

    def test_get_valid_access_token_rejects_non_jwt(self):
        token = TapisOAuth2Token.objects.create(
            user=self.user,
            client=self.oauth_client,
            access_token="Token for testuser (WEBodm.tacc.utexas.edu)",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )

        self.assertIsNone(token.get_valid_access_token())
        self.assertFalse(token.is_valid)

    def test_get_valid_access_token_rejects_missing_expiration(self):
        header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
        payload = _b64url(json.dumps({"tapis/username": "testuser"}).encode("utf-8"))
        token = TapisOAuth2Token.objects.create(
            user=self.user,
            client=self.oauth_client,
            access_token=f"{header}.{payload}.signature",
        )

        self.assertIsNone(token.get_valid_access_token())
        self.assertTrue(token.is_expired)

    def test_oauth_callback_does_not_store_refresh_token(self):
        token_value = _make_jwt()

        TapisOAuth2CallbackView()._store_user_tokens(self.user, self.oauth_client, {
            "access_token": {"access_token": token_value},
            "refresh_token": {"refresh_token": "tenant-refresh-token"},
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid profile",
        })

        stored = TapisOAuth2Token.objects.get(user=self.user, client=self.oauth_client)
        self.assertEqual(stored.access_token, token_value)
        self.assertEqual(stored.refresh_token, "")
        self.assertIsNotNone(stored.expires_at)

    def test_removed_refresh_route_returns_not_found(self):
        self.client.login(username="testuser", password="test1234")

        response = self.client.post("/api/oauth2/tapis/refresh/test-client/")

        self.assertEqual(response.status_code, 404)

    def test_logout_clears_legacy_refresh_token(self):
        token = TapisOAuth2Token.objects.create(
            user=self.user,
            client=self.oauth_client,
            access_token=_make_jwt(),
            refresh_token="legacy-refresh-token",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        self.client.login(username="testuser", password="test1234")

        response = self.client.get("/logout/")

        self.assertEqual(response.status_code, 302)
        token.refresh_from_db()
        self.assertEqual(token.refresh_token, "")
