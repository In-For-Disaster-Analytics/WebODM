import base64
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import override_settings
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from app.models import Project, Task, SplatRun
from app.services import opensplat, nodesplat
from .classes import BootTestCase

SECRET = "s" * 40
JOB = "job-0001"
CLUSTER_SETTINGS = dict(
    OPENSPLAT_ENABLED=True,
    OPENSPLAT_BACKEND='clusterodx',
    NODESPLAT_CLUSTER_URL="https://cluster.example.org",
    NODESPLAT_AUDIENCE="clusterodx-test",
    NODESPLAT_PROFILE="nodesplat-v1",
    NODESPLAT_GRANT_KEY_ID="k1",
    NODESPLAT_GRANT_SECRET=SECRET,
    OPENSPLAT_APP_ID="opensplat-app",
    OPENSPLAT_APP_VERSION="1.0",
)


def js_canonical(value):
    """Mirror of canonical() in ClusterODX/libs/splatAuth.js (ASCII-only protocol)."""
    if value is None or isinstance(value, (bool, str, int)):
        return json.dumps(value)
    if isinstance(value, list):
        return '[' + ','.join(js_canonical(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k) + ':' + js_canonical(value[k]) for k in sorted(value)) + '}'
    raise TypeError(value)


class NodeSplatBase(BootTestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.overrides = override_settings(
            OPENSPLAT_STAGING_ROOT=os.path.join(self.root, "staging"),
            OPENSPLAT_STAGING_LS6_ROOT="/scratch/staging",
            OPENSPLAT_OUTPUT_ROOT=os.path.join(self.root, "output"),
            OPENSPLAT_OUTPUT_ARCHIVE_ROOT="/corral/output",
            TAPIS_BASE_URL="https://tacc.tapis.io",
            **CLUSTER_SETTINGS)
        self.overrides.enable()
        self.user = User.objects.get(username="testuser")
        self.project = Project.objects.create(owner=self.user, name="nodesplat")
        self.task = Task.objects.create(project=self.project)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.import_ = mock.patch("worker.tasks.import_splat_run.delay")
        self.import_mock = self.import_.start()

    def tearDown(self):
        self.import_.stop()
        self.overrides.disable()
        shutil.rmtree(self.root, ignore_errors=True)

    def make_run(self, **kwargs):
        defaults = dict(task=self.task, user=self.user, settings={'num_iterations': 100, 'image_size': 1920},
                        backend='clusterodx', backend_profile='nodesplat-v1')
        defaults.update(kwargs)
        return SplatRun.objects.create(**defaults)

    def url(self, run, suffix="/output"):
        return "/api/projects/{}/tasks/{}/splats/runs/{}{}".format(self.project.id, self.task.id, run.id, suffix)


class TestNodeSplatModelAndConfig(NodeSplatBase):
    def test_new_fields_default_to_direct_backend(self):
        run = self.make_run(backend='direct_tapis', backend_profile='')
        run.refresh_from_db()
        self.assertEqual(run.backend, 'direct_tapis')
        self.assertIsNone(run.cluster_task_uuid)
        self.assertEqual(run.phase, '')
        self.assertIsNone(run.progress)
        # Model defaults themselves (no explicit backend given)
        self.assertEqual(SplatRun._meta.get_field('backend').default, 'direct_tapis')

    def test_active_states_and_constraint(self):
        self.assertIn(SplatRun.RESULT_READY, SplatRun.ACTIVE_STATES)
        self.assertIn(SplatRun.CANCEL_PENDING, SplatRun.ACTIVE_STATES)
        for state in (SplatRun.RESULT_READY, SplatRun.CANCEL_PENDING):
            run = self.make_run(state=state)
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.make_run()
            run.state = SplatRun.FAILED
            run.save()
        self.make_run(state=SplatRun.READY)

    def test_is_configured_clusterodx(self):
        self.assertTrue(opensplat.is_configured())
        for override in (dict(NODESPLAT_CLUSTER_URL=''), dict(NODESPLAT_GRANT_KEY_ID=''),
                         dict(NODESPLAT_GRANT_SECRET=''), dict(NODESPLAT_GRANT_SECRET='short'),
                         dict(NODESPLAT_AUDIENCE=''), dict(NODESPLAT_CLUSTER_URL='ftp://x'),
                         dict(NODESPLAT_CLUSTER_URL='https://u:p@x.org')):
            with override_settings(**override):
                self.assertFalse(opensplat.is_configured(), override)

    def test_is_configured_clusterodx_does_not_need_tapis_roots(self):
        with override_settings(TAPIS_BASE_URL='', OPENSPLAT_STAGING_LS6_ROOT='', OPENSPLAT_OUTPUT_ARCHIVE_ROOT=''):
            self.assertTrue(opensplat.is_configured())

    def test_direct_backend_unchanged(self):
        with override_settings(OPENSPLAT_BACKEND='direct_tapis', NODESPLAT_CLUSTER_URL='', NODESPLAT_GRANT_SECRET=''):
            self.assertTrue(opensplat.is_configured())
            with override_settings(TAPIS_BASE_URL=''):
                self.assertFalse(opensplat.is_configured())
        with override_settings(OPENSPLAT_BACKEND='bogus'):
            self.assertFalse(opensplat.is_configured())

    def test_create_run_pins_backend(self):
        from django.utils import timezone
        from app.models import TapisOAuth2Client, TapisOAuth2Token
        from .test_tapis_oauth2_tokens import _make_jwt
        client = TapisOAuth2Client.objects.create(client_id="c", client_secret="s", tenant_id="t",
            base_url="https://tacc.tapis.io", callback_url="https://x/cb", name="n", description="d")
        TapisOAuth2Token.objects.create(user=self.user, client=client, access_token=_make_jwt(),
            expires_at=timezone.now() + timezone.timedelta(hours=1))
        with mock.patch("worker.tasks.stage_splat_run.delay"):
            run = opensplat.create_run(self.task, self.user, {'num_iterations': '7', 'image_size': '0'})
        self.assertEqual((run.backend, run.backend_profile), ('clusterodx', 'nodesplat-v1'))
        self.assertEqual(run.settings, {'num_iterations': 7, 'image_size': 0})

    def test_create_run_settings_validation(self):
        for bad in ({'num_iterations': 0}, {'num_iterations': 1001}, {'num_iterations': 'x'},
                    {'image_size': 5}, {'image_size': 4097}, {'image_size': -1}):
            with self.assertRaises(opensplat.OpenSplatError):
                opensplat.clean_settings(bad)
        self.assertEqual(opensplat.clean_settings({'num_iterations': 1000, 'image_size': 16}),
                         {'num_iterations': 1000, 'image_size': 16})


class TestClusterGrant(NodeSplatBase):
    def test_grant_envelope_matches_js_verifier(self):
        run = self.make_run()
        user_client = mock.Mock(tenant_id='tenant-x')
        captured = {}

        def fake_request(self_, method, path, **kwargs):
            captured.update(method=method, path=path, **kwargs)
            return {'uuid': str(uuid.uuid4())}

        with mock.patch.object(nodesplat, 'get_user_token', return_value=('tok', user_client)), \
                mock.patch.object(nodesplat.ClusterClient, 'request', fake_request):
            nodesplat.ClusterClient(self.user).submit(run, 'a' * 64)

        self.assertEqual((captured['method'], captured['path']), ('POST', '/splat/task/new'))
        body = captured['json']
        self.assertEqual(set(body), {'run_id', 'source_task_id', 'manifest_sha256', 'profile_id', 'settings', 'grant'})
        grant = body['grant']
        self.assertEqual((grant['version'], grant['key_id']), (1, 'k1'))
        payload = grant['payload']
        self.assertEqual(payload['issuer'], 'webodm')
        self.assertEqual(payload['audience'], 'clusterodx-test')
        self.assertEqual(payload['owner'], {'username': 'testuser', 'tenant': 'tenant-x'})
        self.assertEqual(payload['run_id'], body['run_id'])
        self.assertEqual(payload['settings'], body['settings'])
        self.assertEqual(payload['expires_at'] - payload['issued_at'], 300)
        # JS verifier signs canonical({version, key_id, payload}), base64url, no padding
        signed = js_canonical({'version': 1, 'key_id': 'k1', 'payload': payload}).encode()
        expected = base64.urlsafe_b64encode(hmac.new(SECRET.encode(), signed, hashlib.sha256).digest()).decode().rstrip('=')
        self.assertEqual(grant['signature'], expected)
        self.assertNotIn('=', grant['signature'])

    def test_non_ascii_identifier_rejected(self):
        run = self.make_run()
        user = User.objects.get(username="testuser")
        user.username = "tést"
        with mock.patch.object(nodesplat, 'get_user_token', return_value=('tok', mock.Mock(tenant_id='t'))):
            client = nodesplat.ClusterClient(user)
        with mock.patch.object(nodesplat.ClusterClient, 'request') as request:
            with self.assertRaises(opensplat.OpenSplatError):
                client.submit(run, 'a' * 64)
            request.assert_not_called()

    def test_missing_token_requires_signin(self):
        with mock.patch.object(nodesplat, 'get_user_token', return_value=(None, None)):
            with self.assertRaises(opensplat.SigninRequired):
                nodesplat.ClusterClient(self.user)

    def test_request_error_mapping(self):
        with mock.patch.object(nodesplat, 'get_user_token', return_value=('tok', mock.Mock())):
            client = nodesplat.ClusterClient(self.user)

        def response(code, payload=None):
            r = mock.Mock(status_code=code, ok=200 <= code < 300)
            r.json.return_value = payload if payload is not None else {}
            return r

        cases = [(401, opensplat.SigninRequired), (403, opensplat.OpenSplatError), (502, opensplat.SubmissionUnknown),
                 (400, opensplat.OpenSplatError)]
        for code, exc in cases:
            with mock.patch.object(nodesplat.requests, 'request', return_value=response(code)):
                with self.assertRaises(exc):
                    client.request('GET', '/x')
        with mock.patch.object(nodesplat.requests, 'request', side_effect=nodesplat.requests.ConnectionError()):
            with self.assertRaises(opensplat.SubmissionUnknown):
                client.request('GET', '/x')
        with mock.patch.object(nodesplat.requests, 'request', return_value=response(200, [])):
            with self.assertRaises(opensplat.SubmissionUnknown):
                client.request('GET', '/x')
        with mock.patch.object(nodesplat.requests, 'request', return_value=response(200, {'a': 1})) as req:
            self.assertEqual(client.request('GET', '/x'), {'a': 1})
            self.assertEqual(req.call_args[1]['headers']['Authorization'], 'Bearer tok')
            self.assertFalse(req.call_args[1]['allow_redirects'])

    def test_output_response_validation(self):
        with mock.patch.object(nodesplat, 'get_user_token', return_value=('tok', mock.Mock())):
            client = nodesplat.ClusterClient(self.user)
        good = {'lines': ['a', 'b'], 'next_line': 5, 'truncated': False, 'eof': True}
        with mock.patch.object(nodesplat.ClusterClient, 'request', return_value=good):
            out = client.output(uuid.uuid4(), 3)
        self.assertEqual((out['from_line'], out['next_line'], out['eof']), (3, 5, True))
        for bad in ({'lines': ['a'], 'next_line': 9}, {'lines': [1], 'next_line': 4}, {'lines': 'x', 'next_line': 0},
                    {'lines': ['a'] * 501, 'next_line': 501}, {'lines': ['a' * 262145], 'next_line': 1}):
            with mock.patch.object(nodesplat.ClusterClient, 'request', return_value=bad):
                with self.assertRaises(opensplat.OpenSplatError):
                    client.output(uuid.uuid4(), 0)


class TestApplyClusterStatus(NodeSplatBase):
    def setUp(self):
        super().setUp()
        self.cluster_uuid = uuid.uuid4()
        self.run = self.make_run(state=SplatRun.SUBMITTING)

    def data(self, **kw):
        d = {'uuid': str(self.cluster_uuid), 'run_id': str(self.run.id), 'state': 'queued', 'phase': 'Waiting',
             'tapis_job_uuid': JOB, 'progress': None}
        d.update(kw)
        return d

    def test_accepts_and_binds(self):
        opensplat.apply_cluster_status(self.run, self.data())
        self.run.refresh_from_db()
        self.assertEqual((self.run.state, self.run.cluster_task_uuid, self.run.tapis_job_uuid),
                         ('queued', self.cluster_uuid, JOB))
        self.assertEqual(self.run.phase, 'Waiting')

    def test_rejects_mismatches(self):
        opensplat.apply_cluster_status(self.run, self.data())
        for bad in (self.data(run_id=str(uuid.uuid4())), self.data(uuid=str(uuid.uuid4())),
                    self.data(tapis_job_uuid='other-job'), self.data(state='bogus'), self.data(state=None)):
            with self.assertRaises(opensplat.OpenSplatError):
                opensplat.apply_cluster_status(self.run, bad)
        with self.assertRaises(opensplat.SubmissionUnknown):
            opensplat.apply_cluster_status(self.run, {'uuid': 'not-a-uuid'})
        self.run.refresh_from_db()
        self.assertEqual((self.run.state, self.run.tapis_job_uuid), ('queued', JOB))

    def test_progress_sanitized(self):
        for progress, expected in (({'iteration': 5, 'total': 100}, {'iteration': 5, 'total': 100}),
                                   ({'iteration': 101, 'total': 100}, None), ({'iteration': -1, 'total': 100}, None),
                                   ({'iteration': 1, 'total': 5000}, None), ({'iteration': '1', 'total': 5}, None),
                                   ('50%', None)):
            opensplat.apply_cluster_status(self.run, self.data(state='running', progress=progress))
            self.run.refresh_from_db()
            self.assertEqual(self.run.progress, expected, progress)

    def test_ready_imports_exactly_once(self):
        opensplat.apply_cluster_status(self.run, self.data(state='ready'))
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, SplatRun.IMPORTING)
        self.import_mock.assert_called_once_with(str(self.run.id))
        # A repeated ready response must not requeue (importing is not updated by cluster responses)
        opensplat.apply_cluster_status(self.run, self.data(state='ready'))
        self.assertEqual(self.import_mock.call_count, 1)

    def test_ready_without_job_rejected(self):
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.apply_cluster_status(self.run, self.data(state='ready', tapis_job_uuid=None))
        self.import_mock.assert_not_called()

    def test_failed_uses_generic_error(self):
        opensplat.apply_cluster_status(self.run, self.data(state='failed', error={'message': '/secret/path token'}))
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, SplatRun.FAILED)
        self.assertNotIn('/secret', self.run.error)
        self.assertTrue(self.run.error)

    def test_terminal_run_not_overwritten(self):
        SplatRun.objects.filter(pk=self.run.pk).update(state=SplatRun.CANCELED)
        opensplat.apply_cluster_status(self.run, self.data(state='running'))
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, SplatRun.CANCELED)


class TestFindClusterResult(NodeSplatBase):
    def setUp(self):
        super().setUp()
        self.cluster_uuid = uuid.uuid4()
        self.run = self.make_run(state=SplatRun.IMPORTING, cluster_task_uuid=self.cluster_uuid, tapis_job_uuid=JOB)
        self.out = opensplat.run_output_dir(self.run)
        os.makedirs(self.out)
        self.ply = b'ply\nend_header\n' + b'\x00' * 32
        with open(os.path.join(self.out, 'model.ply'), 'wb') as f:
            f.write(self.ply)

    def write_manifest(self, **overrides):
        m = {'schema_version': 1, 'run_id': str(self.run.id), 'source_task_id': str(self.task.id),
             'cluster_task_uuid': str(self.cluster_uuid), 'tapis_job_uuid': JOB, 'profile_id': 'nodesplat-v1',
             'settings': self.run.settings, 'app': {'id': 'opensplat-app', 'version': '1.0'},
             'output': {'bytes': len(self.ply), 'sha256': hashlib.sha256(self.ply).hexdigest()}}
        m.update(overrides)
        with open(os.path.join(self.out, 'manifest.json'), 'w') as f:
            json.dump(m, f)

    def test_valid(self):
        self.write_manifest()
        path, size = opensplat.find_result(self.run)
        self.assertEqual((os.path.basename(path), size), ('model.ply', len(self.ply)))

    def test_mismatches_rejected(self):
        for override in ({'run_id': str(uuid.uuid4())}, {'source_task_id': str(uuid.uuid4())},
                         {'cluster_task_uuid': str(uuid.uuid4())}, {'tapis_job_uuid': 'x'},
                         {'profile_id': 'other'}, {'settings': {'num_iterations': 1, 'image_size': 1}},
                         {'app': {'id': 'evil', 'version': '1.0'}}, {'app': {'id': 'opensplat-app', 'version': '9'}},
                         {'output': {'bytes': len(self.ply), 'sha256': '0' * 64}},
                         {'output': {'bytes': 1, 'sha256': hashlib.sha256(self.ply).hexdigest()}},
                         {'schema_version': 2}):
            self.write_manifest(**override)
            with self.assertRaises(opensplat.OpenSplatError, msg=override):
                opensplat.find_result(self.run)

    def test_missing_job_and_symlink_rejected(self):
        self.write_manifest()
        SplatRun.objects.filter(pk=self.run.pk).update(tapis_job_uuid='')
        self.run.refresh_from_db()
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.find_result(self.run)
        SplatRun.objects.filter(pk=self.run.pk).update(tapis_job_uuid=JOB)
        self.run.refresh_from_db()
        outside = os.path.join(self.root, 'outside.ply')
        with open(outside, 'wb') as f:
            f.write(self.ply)
        os.unlink(os.path.join(self.out, 'model.ply'))
        os.symlink(outside, os.path.join(self.out, 'model.ply'))
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.find_result(self.run)

    def test_size_limit(self):
        self.write_manifest()
        with override_settings(OPENSPLAT_MAX_RESULT_BYTES=4):
            with self.assertRaises(opensplat.OpenSplatError):
                opensplat.find_result(self.run)


class TestCancelClusterRun(NodeSplatBase):
    def test_cancel_sets_pending_and_calls_cluster(self):
        cu = uuid.uuid4()
        run = self.make_run(state=SplatRun.RUNNING, cluster_task_uuid=cu, tapis_job_uuid=JOB)
        with mock.patch.object(nodesplat, 'get_user_token', return_value=('tok', mock.Mock())), \
                mock.patch.object(nodesplat.ClusterClient, 'cancel', autospec=True,
                                  return_value={'uuid': str(cu), 'state': 'cancel_pending', 'cancel_pending': True}) as cancel:
            result = opensplat.cancel_run(run)
        cancel.assert_called_once()
        self.assertEqual(cancel.call_args[0][1], cu)
        self.assertEqual(result.state, SplatRun.CANCEL_PENDING)
        self.assertTrue(result.is_active)

    def test_cancel_confirmed(self):
        cu = uuid.uuid4()
        run = self.make_run(state=SplatRun.QUEUED, cluster_task_uuid=cu, tapis_job_uuid=JOB)
        with mock.patch.object(nodesplat, 'get_user_token', return_value=('tok', mock.Mock())), \
                mock.patch.object(nodesplat.ClusterClient, 'cancel', return_value={'uuid': str(cu), 'state': 'canceled'}):
            self.assertEqual(opensplat.cancel_run(run).state, SplatRun.CANCELED)

    def test_cancel_refused_while_importing_or_without_task(self):
        for kwargs in ({'state': SplatRun.IMPORTING, 'cluster_task_uuid': uuid.uuid4()}, {'state': SplatRun.SUBMISSION_UNKNOWN}):
            run = self.make_run(**kwargs)
            with self.assertRaises(opensplat.OpenSplatError):
                opensplat.cancel_run(run)
            run.state = SplatRun.FAILED
            run.save()


class TestRunOutputApi(NodeSplatBase):
    def test_owner_reads_proxied_output(self):
        cu = uuid.uuid4()
        run = self.make_run(state=SplatRun.RUNNING, cluster_task_uuid=cu)
        payload = {'lines': ['x'], 'from_line': 2, 'next_line': 3, 'truncated': False, 'eof': False}
        with mock.patch.object(nodesplat, 'get_user_token', return_value=('tok', mock.Mock())), \
                mock.patch.object(nodesplat.ClusterClient, 'output', autospec=True, return_value=dict(payload)) as out:
            res = self.api.get(self.url(run) + "?line=2")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(out.call_args[0][1:], (cu, 2))
        self.assertEqual(res.data['lines'], ['x'])
        self.assertEqual(res.data['run_id'], str(run.id))

    def test_other_user_forbidden_even_with_view(self):
        run = self.make_run(state=SplatRun.RUNNING, cluster_task_uuid=uuid.uuid4())
        other = User.objects.create_user("viewer", password="pw")
        assign_perm('view_project', other, self.project)
        c = APIClient()
        c.force_authenticate(user=other)
        with mock.patch.object(nodesplat.ClusterClient, 'output') as out:
            self.assertEqual(c.get(self.url(run)).status_code, status.HTTP_403_FORBIDDEN)
            out.assert_not_called()

    def test_invalid_cursor(self):
        run = self.make_run(state=SplatRun.RUNNING, cluster_task_uuid=uuid.uuid4())
        for bad in ("-1", "abc", "1.5", "10000001", ""):
            self.assertEqual(self.api.get(self.url(run) + "?line=" + bad).status_code,
                             status.HTTP_400_BAD_REQUEST, bad)

    def test_unknown_run_not_found(self):
        run = self.make_run()
        run.id = uuid.uuid4()
        self.assertEqual(self.api.get(self.url(run)).status_code, status.HTTP_404_NOT_FOUND)

    def test_download_reads_retained_console(self):
        run = self.make_run(state=SplatRun.FAILED, cluster_task_uuid=uuid.uuid4())
        out = opensplat.run_output_dir(run)
        os.makedirs(out)
        with open(os.path.join(out, 'console.txt'), 'wb') as f:
            f.write(b'line one\nline two\n')
        res = self.api.get(self.url(run) + "?download=1")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.content, b'line one\nline two\n')
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertIn('no-store', res['Cache-Control'])

    def test_download_missing_console(self):
        run = self.make_run(state=SplatRun.FAILED, cluster_task_uuid=uuid.uuid4())
        self.assertEqual(self.api.get(self.url(run) + "?download=1").status_code, status.HTTP_400_BAD_REQUEST)

    def test_direct_run_has_no_remote_output(self):
        run = self.make_run(backend='direct_tapis', backend_profile='', state=SplatRun.RUNNING)
        with mock.patch.object(nodesplat.ClusterClient, 'output') as out:
            res = self.api.get(self.url(run) + "?line=4")
        out.assert_not_called()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual((res.data['lines'], res.data['next_line'], res.data['eof']), ([], 4, False))
        self.assertEqual(opensplat.run_output(run, 0)['lines'], [])
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.download_run_log(run)
