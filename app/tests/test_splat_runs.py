import hashlib
import json
import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from app.models import Project, Task, SplatRun, TapisOAuth2Client, TapisOAuth2Token
from app.services import opensplat
from .classes import BootTestCase
from .test_tapis_oauth2_tokens import _make_jwt


class TestSplatRuns(BootTestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.overrides = override_settings(
            OPENSPLAT_ENABLED=True,
            TAPIS_BASE_URL="https://tacc.tapis.io",
            OPENSPLAT_STAGING_ROOT=os.path.join(self.root, "staging"),
            OPENSPLAT_STAGING_LS6_ROOT="/scratch/staging",
            OPENSPLAT_OUTPUT_ROOT=os.path.join(self.root, "output"),
            OPENSPLAT_OUTPUT_ARCHIVE_ROOT="/corral/output",
        )
        self.overrides.enable()

        self.user = User.objects.get(username="testuser")
        self.project = Project.objects.create(owner=self.user, name="splat runs")
        self.task = self.make_task(self.project)

        self.oauth_client = TapisOAuth2Client.objects.create(
            client_id="c", client_secret="s", tenant_id="t", base_url="https://tacc.tapis.io",
            callback_url="https://x/cb", name="n", description="d")
        self.token = TapisOAuth2Token.objects.create(
            user=self.user, client=self.oauth_client, access_token=_make_jwt(),
            expires_at=timezone.now() + timezone.timedelta(hours=1))

        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

        # Run Celery work inline without hitting a broker
        self.stage = mock.patch("worker.tasks.stage_splat_run.delay")
        self.import_ = mock.patch("worker.tasks.import_splat_run.delay")
        self.stage_mock = self.stage.start()
        self.import_mock = self.import_.start()

    def tearDown(self):
        self.stage.stop()
        self.import_.stop()
        self.overrides.disable()
        shutil.rmtree(self.root, ignore_errors=True)

    def make_task(self, project, filenames=("a.jpg", "b.jpg")):
        task = Task.objects.create(project=project)
        os.makedirs(task.assets_path("odm_georeferencing"), exist_ok=True)
        os.makedirs(task.assets_path("odm_report"), exist_ok=True)
        cam = "dji test 48 36 perspective 0.85"
        with open(task.get_asset_file_or_stream('cameras.json'), 'w') as f:
            json.dump({cam: {'projection_type': 'perspective', 'width': 48, 'height': 36, 'focal': 0.85}}, f)
        with open(task.get_asset_file_or_stream('shots.geojson'), 'w') as f:
            json.dump({'type': 'FeatureCollection', 'features': [{
                'type': 'Feature', 'geometry': None,
                'properties': {'filename': n, 'camera': 'v2 ' + cam, 'translation': [1, 2, 3], 'rotation': [0, 0, 0]}
            } for n in filenames]}, f)
        with open(task.get_asset_file_or_stream('georeferenced_model.laz'), 'wb') as f:
            f.write(b'laz')
        with open(task.assets_path("odm_georeferencing", "coords.txt"), 'w') as f:
            f.write("WGS84 UTM 14N\n348892 6744240\n")
        for n in filenames:
            with open(task.task_path(n), 'wb') as f:
                f.write(b'\xff\xd8jpeg-' + n.encode())
        task.update_available_assets_field(commit=True)
        task.refresh_from_db()
        return task

    def url(self, suffix=""):
        return "/api/projects/{}/tasks/{}/splats/runs{}".format(self.project.id, self.task.id, suffix)

    def make_run(self, **kwargs):
        defaults = dict(task=self.task, user=self.user, settings={'num_iterations': 100, 'image_size': 1920})
        defaults.update(kwargs)
        return SplatRun.objects.create(**defaults)

    # --- API -----------------------------------------------------------

    def test_disabled_feature_hides_and_rejects(self):
        with override_settings(OPENSPLAT_ENABLED=False):
            res = self.api.get(self.url())
            self.assertFalse(res.data['enabled'])
            self.assertEqual(self.api.post(self.url(), {}).status_code, status.HTTP_404_NOT_FOUND)

    def test_create_requires_edit_permission(self):
        other = User.objects.create_user("reader", password="pw")
        assign_perm('view_project', other, self.project)
        c = APIClient()
        c.force_authenticate(user=other)
        self.assertEqual(c.get(self.url()).status_code, status.HTTP_200_OK)
        self.assertEqual(c.post(self.url(), {}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(SplatRun.objects.count(), 0)

    def test_create_validates_settings_and_token(self):
        res = self.api.post(self.url(), {'num_iterations': 10 ** 9})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.token.expires_at = timezone.now() - timezone.timedelta(hours=1)
        self.token.access_token = _make_jwt(exp_seconds=-10)
        self.token.save()
        res = self.api.post(self.url(), {})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(res.data['signin_required'])
        self.assertEqual(SplatRun.objects.count(), 0)

    def test_create_and_single_active_run(self):
        res = self.api.post(self.url(), {'num_iterations': 5, 'bogus': 'x'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        run = SplatRun.objects.get()
        self.assertEqual(run.settings, {'num_iterations': 5, 'image_size': 1920})
        self.assertEqual(run.state, SplatRun.PREPARING)
        self.stage_mock.assert_called_once_with(str(run.id))
        # Never leaks internal paths or tokens
        self.assertNotIn('snapshot_path', res.data['run'])

        res = self.api.post(self.url(), {})
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(SplatRun.objects.count(), 1)

    def test_database_enforces_single_active_run(self):
        from django.db import IntegrityError, transaction
        self.make_run()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_run()
        self.make_run(state=SplatRun.FAILED)  # finished runs are not limited

    def test_sync_and_cancel_are_owner_only_and_task_scoped(self):
        run = self.make_run(state=SplatRun.RUNNING, tapis_job_uuid="job-1")
        other = User.objects.create_user("editor", password="pw")
        assign_perm('view_project', other, self.project)
        assign_perm('change_project', other, self.project)
        c = APIClient()
        c.force_authenticate(user=other)

        res = c.get(self.url())
        self.assertFalse(res.data['run']['is_owner'])
        self.assertNotIn('tapis_job_uuid', res.data['run'])
        self.assertEqual(c.post(self.url("/{}/sync".format(run.id))).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(c.post(self.url("/{}/cancel".format(run.id))).status_code, status.HTTP_403_FORBIDDEN)

        # A run id from another task is not found
        other_task = self.make_task(self.project)
        wrong = "/api/projects/{}/tasks/{}/splats/runs/{}/sync".format(self.project.id, other_task.id, run.id)
        self.assertEqual(self.api.post(wrong).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.api.post(self.url("/not-a-uuid/sync")).status_code, status.HTTP_404_NOT_FOUND)

    # --- staging -------------------------------------------------------

    def test_stage_snapshot_and_manifest(self):
        run = self.make_run()
        input_dir = opensplat.stage_run_input(run)

        with open(os.path.join(input_dir, 'webodm-input.json')) as f:
            manifest = json.load(f)
        self.assertEqual(manifest['task_id'], str(self.task.id))
        self.assertEqual(manifest['rtc_offset'], [348892.0, 6744240.0])
        self.assertEqual(manifest['image_size'], 1920)
        self.assertEqual([i['filename'] for i in manifest['images']], ['a.jpg', 'b.jpg'])
        for rel in ['cameras.json', 'shots.geojson', 'cloud.laz', 'images/a.jpg', 'images/b.jpg']:
            p = os.path.join(input_dir, rel)
            self.assertTrue(os.path.isfile(p))
            self.assertEqual(os.stat(p).st_nlink, 1)  # copied, not hard linked
        self.assertFalse(os.path.exists(os.path.join(input_dir, 'webodm-input.json.tmp')))

    def test_stage_rejects_bad_inputs(self):
        # Missing image
        os.unlink(self.task.task_path('b.jpg'))
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.stage_run_input(self.make_run(state=SplatRun.FAILED))

        # Symlink escape
        outside = os.path.join(self.root, 'secret.jpg')
        with open(outside, 'wb') as f:
            f.write(b'secret')
        os.symlink(outside, self.task.task_path('b.jpg'))
        run = self.make_run(state=SplatRun.FAILED)
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.stage_run_input(run)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'staging', str(run.id))))

        # Duplicate filenames and unknown cameras
        dup = self.make_task(self.project, filenames=("a.jpg", "a.jpg"))
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.collect_inputs(dup)
        bad = self.make_task(self.project)
        with open(bad.get_asset_file_or_stream('cameras.json'), 'w') as f:
            json.dump({"other": {}}, f)
        with self.assertRaises(opensplat.OpenSplatError):
            opensplat.collect_inputs(bad)

        # Limits
        with override_settings(OPENSPLAT_MAX_IMAGES=1):
            with self.assertRaises(opensplat.OpenSplatError):
                opensplat.collect_inputs(self.make_task(self.project))
        with override_settings(OPENSPLAT_MAX_INPUT_BYTES=4):
            with self.assertRaises(opensplat.OpenSplatError):
                opensplat.collect_inputs(self.make_task(self.project))

    # --- submission ----------------------------------------------------

    def submit(self, run, response=None, side_effect=None):
        with mock.patch("app.services.opensplat.requests.request") as req:
            if side_effect:
                req.side_effect = side_effect
            else:
                req.return_value = response
            opensplat.submit_run(str(run.id))
            return req

    @staticmethod
    def resp(status_code=200, result=None):
        r = mock.Mock(status_code=status_code, ok=status_code < 400)
        r.json.return_value = {'result': result}
        return r

    def test_submit_uses_user_token_and_validated_paths(self):
        run = self.make_run()
        req = self.submit(run, self.resp(result={'uuid': 'job-1'}))
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.QUEUED)
        self.assertEqual(run.tapis_job_uuid, 'job-1')

        args, kwargs = req.call_args
        self.assertEqual(args[0], 'POST')
        self.assertTrue(args[1].endswith('/v3/jobs/submit'))
        self.assertEqual(kwargs['headers']['X-Tapis-Token'], self.token.access_token)
        self.assertEqual(kwargs['timeout'], 30)
        body = kwargs['json']
        self.assertEqual(body['name'], "webodm-splat-{}".format(run.id))
        self.assertEqual(body['archiveSystemDir'], "/corral/output/{}".format(run.id))
        self.assertEqual(body['parameterSet']['appArgs'][0]['arg'], "/scratch/staging/{}/input".format(run.id))
        # No token ends up in the persisted run
        self.assertNotIn(self.token.access_token, json.dumps(run.settings) + run.error)

    def test_submit_without_token_waits_for_signin_without_submitting(self):
        TapisOAuth2Token.objects.all().delete()
        run = self.make_run()
        req = self.submit(run, self.resp(result={'uuid': 'x'}))
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.AWAITING_SIGNIN)
        self.assertTrue(run.snapshot_path)
        req.assert_not_called()

    def test_ambiguous_submission_is_not_retried_and_reconciles(self):
        import requests
        run = self.make_run()
        self.submit(run, side_effect=requests.Timeout())
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.SUBMISSION_UNKNOWN)

        # Submission is not repeated by another delivery of the same task
        req = self.submit(run, self.resp(result={'uuid': 'dup'}))
        req.assert_not_called()

        job = {'uuid': 'job-9', 'name': opensplat.job_name(run), 'appId': 'opensplat-ls6',
               'appVersion': '0.2.0', 'status': 'RUNNING'}
        with mock.patch("app.services.opensplat.requests.request", return_value=self.resp(result=[job])) as req:
            run = opensplat.sync_run(run)
        self.assertEqual((run.state, run.tapis_job_uuid), (SplatRun.RUNNING, 'job-9'))
        self.assertIn('name.eq.webodm-splat-', req.call_args[1]['params']['search'])

    def test_ambiguous_submission_with_no_job_fails_safely(self):
        run = self.make_run(state=SplatRun.SUBMISSION_UNKNOWN)
        with mock.patch("app.services.opensplat.requests.request", return_value=self.resp(result=[])):
            run = opensplat.sync_run(run)
        self.assertEqual(run.state, SplatRun.FAILED)

    # --- sync ----------------------------------------------------------

    def sync(self, run, job):
        with mock.patch("app.services.opensplat.requests.request", return_value=self.resp(result=job)):
            return opensplat.sync_run(run)

    def job_for(self, run, status_, **kwargs):
        job = {'uuid': run.tapis_job_uuid, 'name': opensplat.job_name(run), 'appId': 'opensplat-ls6',
               'appVersion': '0.2.0', 'status': status_}
        job.update(kwargs)
        return job

    def test_status_mapping_and_single_import_dispatch(self):
        run = self.make_run(state=SplatRun.QUEUED, tapis_job_uuid="job-1")
        run = self.sync(run, self.job_for(run, 'RUNNING'))
        self.assertEqual(run.state, SplatRun.RUNNING)
        self.import_mock.assert_not_called()

        run = self.sync(run, self.job_for(run, 'FINISHED'))
        self.assertEqual(run.state, SplatRun.IMPORTING)
        self.import_mock.assert_called_once_with(str(run.id))

        # Syncing again does not queue a second import
        self.sync(run, self.job_for(run, 'FINISHED'))
        self.import_mock.assert_called_once()

    def test_failed_job_hides_remote_message(self):
        run = self.make_run(state=SplatRun.RUNNING, tapis_job_uuid="job-1")
        run = self.sync(run, self.job_for(run, 'FAILED', lastMessage="/scratch/secret/path exploded"))
        self.assertEqual(run.state, SplatRun.FAILED)
        self.assertNotIn("secret", run.error)

    def test_sync_rejects_mismatched_job(self):
        run = self.make_run(state=SplatRun.RUNNING, tapis_job_uuid="job-1")
        with self.assertRaises(opensplat.OpenSplatError):
            self.sync(run, self.job_for(run, 'FINISHED', appId='other-app'))
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.RUNNING)

    def test_expired_token_during_sync_requires_signin(self):
        run = self.make_run(state=SplatRun.RUNNING, tapis_job_uuid="job-1")
        TapisOAuth2Token.objects.all().delete()
        res = self.api.post(self.url("/{}/sync".format(run.id)))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(res.data['signin_required'])

    def test_resume_after_signin(self):
        run = self.make_run(state=SplatRun.AWAITING_SIGNIN)
        res = self.api.post(self.url("/{}/sync".format(run.id)))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.PREPARING)
        self.stage_mock.assert_called_once_with(str(run.id))

    def test_cancel(self):
        run = self.make_run(state=SplatRun.RUNNING, tapis_job_uuid="job-1")
        with mock.patch("app.services.opensplat.requests.request", return_value=self.resp(result=None)) as req:
            res = self.api.post(self.url("/{}/cancel".format(run.id)))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(req.call_args[0][1].endswith('/v3/jobs/job-1/cancel'))
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.CANCELED)

        # Unknown submissions must be reconciled first
        unknown = self.make_run(state=SplatRun.SUBMISSION_UNKNOWN)
        self.assertEqual(self.api.post(self.url("/{}/cancel".format(unknown.id))).status_code, status.HTTP_409_CONFLICT)

    # --- import --------------------------------------------------------

    def write_result(self, run, content=b'ply-data', task_id=None, tamper=False):
        out_dir = opensplat.run_output_dir(run)
        os.makedirs(out_dir, exist_ok=True)
        ply = os.path.join(out_dir, "opensplat-{}.ply".format(run.tapis_job_uuid))
        with open(ply, 'wb') as f:
            f.write(content)
        manifest = {
            'job_id': run.tapis_job_uuid, 'tapis_job_uuid': run.tapis_job_uuid,
            'app': {'id': 'opensplat-ls6', 'version': '0.2.0'},
            'input_project': "/scratch/staging/{}/input".format(run.id),
            'preparation': {'task_id': task_id or str(self.task.id)},
            'output': {'path': ply, 'bytes': len(content),
                       'sha256': hashlib.sha256(b'other' if tamper else content).hexdigest()},
        }
        with open(os.path.join(out_dir, "opensplat-{}.manifest.json".format(run.tapis_job_uuid)), 'w') as f:
            json.dump(manifest, f)

    def importing_run(self):
        return self.make_run(state=SplatRun.IMPORTING, tapis_job_uuid="job-1")

    def test_import_success_marks_ready_only_after_conversion(self):
        run = self.importing_run()
        self.write_result(run)
        with mock.patch("worker.tasks.convert_splats") as convert:
            opensplat.import_run(str(run.id))
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.READY)
        task_id, tmp_file = convert.call_args[0]
        self.assertEqual(task_id, self.task.id)
        self.assertFalse(os.path.exists(tmp_file))  # private copy is cleaned up

        # A duplicate delivery does nothing
        with mock.patch("worker.tasks.convert_splats") as convert:
            opensplat.import_run(str(run.id))
        convert.assert_not_called()

    def test_import_conversion_failure_preserves_existing_model(self):
        model = self.task.get_asset_file_or_stream('splats.rad')
        os.makedirs(os.path.dirname(model), exist_ok=True)
        with open(model, 'wb') as f:
            f.write(b'existing')

        run = self.importing_run()
        self.write_result(run)
        with mock.patch("worker.tasks.convert_splats", side_effect=Exception("boom")):
            opensplat.import_run(str(run.id))
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.FAILED)
        self.assertNotIn("boom", run.error)
        with open(model, 'rb') as f:
            self.assertEqual(f.read(), b'existing')

    def test_import_rejects_bad_results(self):
        cases = [
            dict(tamper=True),                       # checksum mismatch
            dict(task_id="00000000-0000-0000-0000-000000000000"),  # wrong task
        ]
        for kwargs in cases:
            run = self.make_run(state=SplatRun.IMPORTING, tapis_job_uuid="job-{}".format(len(kwargs)), )
            self.write_result(run, **kwargs)
            with mock.patch("worker.tasks.convert_splats") as convert:
                opensplat.import_run(str(run.id))
            convert.assert_not_called()
            run.refresh_from_db()
            self.assertEqual(run.state, SplatRun.FAILED)
            SplatRun.objects.filter(pk=run.pk).update(state=SplatRun.CANCELED)

    def test_import_rejects_missing_provenance_and_symlinks(self):
        run = self.importing_run()
        out_dir = opensplat.run_output_dir(run)
        os.makedirs(out_dir)
        outside = os.path.join(self.root, 'evil.ply')
        with open(outside, 'wb') as f:
            f.write(b'evil')
        os.symlink(outside, os.path.join(out_dir, "opensplat-job-1.ply"))
        with mock.patch("worker.tasks.convert_splats") as convert:
            opensplat.import_run(str(run.id))
        convert.assert_not_called()
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.FAILED)

    def test_import_rejects_oversized_result(self):
        run = self.importing_run()
        self.write_result(run, content=b'12345')
        with override_settings(OPENSPLAT_MAX_RESULT_BYTES=2), mock.patch("worker.tasks.convert_splats") as convert:
            opensplat.import_run(str(run.id))
        convert.assert_not_called()
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.FAILED)

    # --- recovery, reconciliation, cleanup -----------------------------

    def age(self, run, **delta):
        SplatRun.objects.filter(pk=run.pk).update(updated_at=timezone.now() - timezone.timedelta(**delta))

    def test_stale_import_is_requeued_but_fresh_one_is_not(self):
        run = self.make_run(state=SplatRun.IMPORTING, tapis_job_uuid="job-1", conversion_celery_id='claimed')
        opensplat.sync_run(run)
        self.import_mock.assert_not_called()

        self.age(run, hours=1)
        run.refresh_from_db()
        opensplat.sync_run(run)
        self.import_mock.assert_called_once_with(str(run.id))
        run.refresh_from_db()
        self.assertEqual(run.conversion_celery_id, '')

        # The re-dispatched import can claim and finish
        self.write_result(run)
        with mock.patch("worker.tasks.convert_splats"):
            opensplat.import_run(str(run.id))
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.READY)

    def test_reconciler_advances_runs_and_skips_signed_out_owners(self):
        run = self.make_run(state=SplatRun.RUNNING, tapis_job_uuid="job-1")
        with mock.patch("app.services.opensplat.requests.request",
                        return_value=self.resp(result=self.job_for(run, 'FINISHED'))):
            opensplat.reconcile_runs()
        run.refresh_from_db()
        self.assertEqual(run.state, SplatRun.IMPORTING)
        self.import_mock.assert_called_once_with(str(run.id))

        other = self.make_task(self.project)
        waiting = self.make_run(task=other, state=SplatRun.RUNNING, tapis_job_uuid="job-2")
        TapisOAuth2Token.objects.all().delete()
        with mock.patch("app.services.opensplat.requests.request") as req:
            opensplat.reconcile_runs()
        req.assert_not_called()
        waiting.refresh_from_db()
        self.assertEqual(waiting.state, SplatRun.RUNNING)

    def test_reconciler_is_a_noop_when_disabled(self):
        self.make_run(state=SplatRun.RUNNING, tapis_job_uuid="job-1")
        with override_settings(OPENSPLAT_ENABLED=False), mock.patch("app.services.opensplat.requests.request") as req:
            opensplat.reconcile_runs()
        req.assert_not_called()

    def test_cleanup_removes_only_old_finished_runs(self):
        old = self.make_run(state=SplatRun.READY)
        recent = self.make_run(task=self.make_task(self.project), state=SplatRun.FAILED)
        active = self.make_run(task=self.make_task(self.project), state=SplatRun.RUNNING)
        dirs = {}
        for r in (old, recent, active):
            dirs[r.id] = (os.path.dirname(opensplat.run_input_dir(r)), opensplat.run_output_dir(r))
            for d in dirs[r.id]:
                os.makedirs(d)
        for r in (old, active):
            self.age(r, days=60)

        outside = os.path.join(self.root, 'precious')
        os.makedirs(outside)
        os.symlink(outside, os.path.join(self.root, 'output', 'link'))

        self.assertEqual(len(opensplat.cleanup_runs(30, dry_run=True)), 2)
        self.assertTrue(all(os.path.isdir(d) for d in dirs[old.id]))

        opensplat.cleanup_runs(30)
        self.assertFalse(any(os.path.exists(d) for d in dirs[old.id]))
        self.assertTrue(all(os.path.isdir(d) for d in dirs[recent.id]))
        self.assertTrue(all(os.path.isdir(d) for d in dirs[active.id]))
        self.assertTrue(os.path.isdir(outside))

