from unittest import mock

from django.contrib.auth.models import User
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from app.models import Project, Task
from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
from app.tests.classes import BootTestCase
from app.tests.test_tapis_oauth2_tokens import _make_jwt
from nodeodm import status_codes


class TestTaskSubmittedBy(BootTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.get(username="testuser")
        self.teammate = User.objects.get(username="testuser2")
        self.project = Project.objects.create(owner=self.owner, name="shared")
        assign_perm('view_project', self.teammate, self.project)
        assign_perm('change_project', self.teammate, self.project)
        self.oauth_client = TapisOAuth2Client.objects.create(
            client_id="c", client_secret="s", tenant_id="t",
            base_url="https://tacc.tapis.io",
            callback_url="https://webodm.example.com/api/oauth2/tapis/callback",
            name="c", description="c",
        )

    def _token_for(self, user):
        value = _make_jwt()
        TapisOAuth2Token.objects.create(
            user=user, client=self.oauth_client, access_token=value,
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        return value

    def test_token_defaults_to_project_owner(self):
        owner_token = self._token_for(self.owner)
        self._token_for(self.teammate)
        task = Task.objects.create(project=self.project)
        self.assertEqual(task._get_tapis_jwt_token(), owner_token)

    def test_token_prefers_submitted_by(self):
        self._token_for(self.owner)
        teammate_token = self._token_for(self.teammate)
        task = Task.objects.create(project=self.project, submitted_by=self.teammate)
        self.assertEqual(task._get_tapis_jwt_token(), teammate_token)

    def test_no_silent_fallback_to_owner_when_submitter_has_no_token(self):
        self._token_for(self.owner)
        task = Task.objects.create(project=self.project, submitted_by=self.teammate)
        self.assertIsNone(task._get_tapis_jwt_token())

    def test_restart_by_teammate_claims_task(self):
        task = Task.objects.create(project=self.project, status=status_codes.FAILED)
        client = APIClient()
        client.force_login(User.objects.get(username="testuser2"))
        with mock.patch("worker.tasks.process_task.delay"):
            res = client.post("/api/projects/{}/tasks/{}/restart/".format(self.project.id, task.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.submitted_by, self.teammate)

    def test_cancel_does_not_change_submitted_by(self):
        task = Task.objects.create(project=self.project, submitted_by=self.owner)
        client = APIClient()
        client.force_login(User.objects.get(username="testuser2"))
        with mock.patch("worker.tasks.process_task.delay"):
            res = client.post("/api/projects/{}/tasks/{}/cancel/".format(self.project.id, task.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.submitted_by, self.owner)

    def test_restart_without_permission_does_not_claim(self):
        other_project = Project.objects.create(owner=self.owner, name="private")
        task = Task.objects.create(project=other_project)
        client = APIClient()
        client.force_login(User.objects.get(username="testuser2"))
        with mock.patch("worker.tasks.process_task.delay"):
            res = client.post("/api/projects/{}/tasks/{}/restart/".format(other_project.id, task.id))
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        task.refresh_from_db()
        self.assertIsNone(task.submitted_by)

    def test_serializer_exposes_username(self):
        task = Task.objects.create(project=self.project, submitted_by=self.teammate)
        client = APIClient()
        client.force_login(User.objects.get(username="testuser"))
        res = client.get("/api/projects/{}/tasks/{}/".format(self.project.id, task.id))
        self.assertEqual(res.data["submitted_by"], "testuser2")
