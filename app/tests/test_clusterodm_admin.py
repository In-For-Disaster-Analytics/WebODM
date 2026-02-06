import base64
import json
import time

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
from webodm import settings
from .classes import BootTestCase


def _b64url(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _make_jwt(exp_seconds=3600):
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
    exp = int(time.time()) + exp_seconds
    payload = _b64url(json.dumps({"exp": exp, "tapis/username": "testsuperuser"}).encode("utf-8"))
    return f"{header}.{payload}.signature"


class TestClusterODMAdmin(BootTestCase):
    def setUp(self):
        self.original_clusterodm_url = settings.CLUSTERODM_URL
        settings.CLUSTERODM_URL = "https://clusterodm.example.com"
        self.client = Client()

        self.superuser = User.objects.get(username="testsuperuser")
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

    def tearDown(self):
        settings.CLUSTERODM_URL = self.original_clusterodm_url

    def test_denies_non_superuser(self):
        self.client.login(username="testuser", password="test1234")
        res = self.client.get("/clusterodm/admin/")
        self.assertEqual(res.status_code, 403)

    def test_redirects_when_no_token(self):
        self.client.login(username="testsuperuser", password="test1234")
        res = self.client.get("/clusterodm/admin/", follow=True)
        self.assertRedirects(res, "/dashboard/")

    def test_redirects_when_clusterodm_url_missing(self):
        settings.CLUSTERODM_URL = ""
        self.client.login(username="testsuperuser", password="test1234")
        token = _make_jwt()
        TapisOAuth2Token.objects.create(
            user=self.superuser,
            client=self.oauth_client,
            access_token=token,
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        res = self.client.get("/clusterodm/admin/", follow=True)
        self.assertRedirects(res, "/dashboard/")

    def test_renders_redirect_with_valid_token(self):
        self.client.login(username="testsuperuser", password="test1234")
        token = _make_jwt()
        TapisOAuth2Token.objects.create(
            user=self.superuser,
            client=self.oauth_client,
            access_token=token,
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        res = self.client.get("/clusterodm/admin/")
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "app/clusterodm_redirect.html")
        self.assertEqual(res.context["clusterodm_url"], "https://clusterodm.example.com")
        self.assertEqual(res.context["tapis_token"], token)
