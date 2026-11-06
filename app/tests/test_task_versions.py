import csv
import io
import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from PIL import Image
import requests
from pyodx.exceptions import NodeConnectionError, NodeResponseError
from rest_framework import status
from rest_framework.test import APIClient

from app import pending_actions
from app.models import Project, Task, TaskRun
from nodeodm import status_codes
from nodeodm.models import ProcessingNode
from .classes import BootTestCase

OPTIONS = [
    {"name": "pc-quality", "value": "high"},
    {"name": "tapis-allocation", "value": "ABC-123"},
]
NODE_UUID = "9ef37fe9-807c-45da-9276-63dc6ee96ab1"
NEW_UUID = "11111111-2222-3333-4444-555555555555"
TAPIS_OPTIONS = [{"name": "tapis-allocation"}, {"name": "rerun-from"}]


class VersionTestCase(BootTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.get(username="testuser")
        self.project = Project.objects.create(owner=self.user, name="Versions")

    def make_task(self, name="Mapping", status=status_codes.COMPLETED, **kwargs):
        t = Task.objects.create(project=self.project, name=name, status=status, options=OPTIONS,
                                images_count=1, processing_time=60000, **kwargs)
        os.makedirs(t.task_path(), exist_ok=True)
        Image.new("RGB", (2, 2)).save(t.task_path("a.jpg"))
        return t

    def make_node(self, tapis=True):
        return ProcessingNode.objects.create(hostname="node", port=3000,
                                             available_options=TAPIS_OPTIONS if tapis else [{"name": "dsm"}])


class TestDuplicateAsVersion(VersionTestCase):
    def test_numbering_and_lineage_across_a_chain(self):
        root = self.make_task(uuid=NODE_UUID)
        v2 = root.duplicate(as_version=True)
        self.assertEqual(v2.name, "Mapping v2")
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.parent_task_id, root.id)
        self.assertEqual(v2.parent_task_ref, root.id)
        self.assertEqual(v2.parent_task_uuid, NODE_UUID)
        self.assertEqual(v2.parent_task_name, "Mapping")
        self.assertEqual(v2.parent_options, OPTIONS)
        self.assertTrue(v2.images_from_parent)
        # The version gets its node task when it is resumed, not the parent's
        self.assertEqual(v2.uuid, "")
        self.assertIsNone(v2.pending_action)
        self.assertTrue(os.path.isfile(v2.task_path("a.jpg")))

        v2.uuid = "uuid-v2"
        v2.save()
        v3 = v2.duplicate(as_version=True)
        self.assertEqual((v3.name, v3.version), ("Mapping v3", 3))
        self.assertEqual(v3.parent_task_ref, v2.id)
        self.assertEqual(v3.parent_task_uuid, "uuid-v2")
        self.assertEqual(v3.parent_task_name, "Mapping v2")

        # A new version from the original continues the lineage numbering
        v4 = root.duplicate(as_version=True)
        self.assertEqual((v4.name, v4.version), ("Mapping v4", 4))

    def test_plain_duplicate_has_no_lineage(self):
        root = self.make_task(uuid=NODE_UUID)
        v2 = root.duplicate(as_version=True)
        copy = v2.duplicate()
        self.assertEqual(copy.name, "Copy of Mapping v2")
        self.assertEqual(copy.version, 1)
        self.assertIsNone(copy.parent_task_ref)
        self.assertFalse(copy.images_from_parent)

    def test_copy_happens_after_the_row_is_committed(self):
        root = self.make_task()
        baseline = len(connection.savepoint_ids)
        seen = {}

        def fake_copytree(src, dst, **kwargs):
            seen["open_transactions"] = len(connection.savepoint_ids) - baseline
            seen["row_exists"] = Task.objects.filter(name="Mapping v2").exists()

        with patch("app.models.task.shutil.copytree", side_effect=fake_copytree):
            v2 = root.duplicate(as_version=True)

        self.assertTrue(v2)
        self.assertEqual(seen, {"open_transactions": 0, "row_exists": True})

    def test_row_is_removed_when_the_copy_fails(self):
        root = self.make_task()
        with patch("app.models.task.shutil.copytree", side_effect=OSError("disk full")):
            with self.assertLogs("app.logger", level="WARNING") as logs:
                self.assertFalse(root.duplicate(as_version=True))
        self.assertTrue(any("disk full" in line for line in logs.output))
        self.assertEqual(Task.objects.filter(project=self.project).count(), 1)

    def test_deleting_the_parent_keeps_provenance(self):
        root = self.make_task(uuid=NODE_UUID)
        v2 = root.duplicate(as_version=True)
        v2.uuid = NEW_UUID
        v2.status = status_codes.COMPLETED
        v2.resume_info = {"checkpoint_uuid": NODE_UUID, "resumed_from_stage": "odm_dem",
                          "resume_mode": "resume", "checkpoint_engine_version": "3.5.6"}
        v2.save()
        root_id = root.id
        run = TaskRun.record_from(v2)

        root.delete()
        v2.refresh_from_db()
        self.assertIsNone(v2.parent_task)
        self.assertEqual(v2.parent_task_ref, root_id)
        self.assertEqual((v2.parent_task_uuid, v2.parent_task_name, v2.version), (NODE_UUID, "Mapping", 2))
        self.assertEqual(v2.parent_options, OPTIONS)
        run.refresh_from_db()
        self.assertEqual(run.parent_task_ref, root_id)
        self.assertEqual(run.parent_task_name, "Mapping")

        out = io.StringIO()
        call_command("exportruns", stdout=out)
        rows = list(csv.reader(io.StringIO(out.getvalue())))
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual(row["version"], "2")
        self.assertEqual(row["parent_task_name"], "Mapping")
        self.assertEqual(row["parent_task_ref"], str(root_id))
        self.assertEqual(row["resume_mode"], "resume")
        self.assertEqual(row["resumed_from_stage"], "odm_dem")

        # ...and after the version itself is gone
        v2.delete()
        out = io.StringIO()
        call_command("exportruns", stdout=out)
        row = dict(zip(*list(csv.reader(io.StringIO(out.getvalue())))[:2]))
        self.assertEqual(row["parent_task_name"], "Mapping")
        self.assertEqual(row["checkpoint_uuid"], NODE_UUID)


class TestResumeApi(VersionTestCase):
    def setUp(self):
        super().setUp()
        # client.login() needs ModelBackend, which this settings module does not enable
        self.client = APIClient()
        self.client.force_authenticate(User.objects.get(username="testsuperuser"))
        self.node = self.make_node()

    def url(self, task, action="resume"):
        return "/api/projects/{}/tasks/{}/{}/".format(self.project.id, task.id, action)

    def test_duplicate_as_version_api(self):
        root = self.make_task()
        res = self.client.post(self.url(root, "duplicate"), {"as_version": True}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["task"]["name"], "Mapping v2")
        self.assertEqual(res.data["task"]["version"], 2)
        self.assertEqual(res.data["task"]["parent_task"], root.id)
        self.assertEqual(res.data["task"]["parent_task_name"], "Mapping")

        res = self.client.post(self.url(root, "duplicate"))
        self.assertEqual(res.data["task"]["name"], "Copy of Mapping")

    def test_resume_info_maps_node_answer_and_is_cached(self):
        task = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        answer = {"resumable": True, "reason": None, "expiresAt": "2026-12-01T00:00:00Z",
                  "stagesCompleted": ["dataset", "opensfm"], "engineVersion": "3.5.6",
                  "checkpointBytes": 1234, "split": 4, "resumableClasses": ["sfm"]}
        with patch.object(ProcessingNode, "get_task_resume_info", return_value=answer) as lookup:
            res = self.client.get(self.url(task))
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data, {
                "resumable": True, "reason": None, "expires_at": "2026-12-01T00:00:00Z",
                "stages_completed": ["dataset", "opensfm"], "engine_version": "3.5.6",
                "checkpoint_bytes": 1234, "split": 4, "resumable_classes": ["sfm"]})
            self.client.get(self.url(task))
            self.assertEqual(lookup.call_count, 1)

    def test_resume_info_reasons(self):
        plain = ProcessingNode.objects.create(hostname="plain", port=3001, available_options=[{"name": "dsm"}])
        task = self.make_task(uuid=NODE_UUID, processing_node=plain)
        with patch.object(ProcessingNode, "get_task_resume_info") as lookup:
            res = self.client.get(self.url(task))
            self.assertEqual(res.data, {"resumable": False, "reason": "not_tapis"})
            lookup.assert_not_called()

        task = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        with patch.object(ProcessingNode, "get_task_resume_info", return_value={"resumable": False, "reason": "disabled"}):
            res = self.client.get(self.url(task))
            self.assertFalse(res.data["resumable"])
            self.assertEqual(res.data["reason"], "disabled")

        task = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        with patch.object(ProcessingNode, "get_task_resume_info", return_value=None):
            res = self.client.get(self.url(task))
            self.assertEqual(res.data, {"resumable": False, "reason": "unavailable"})

    def test_resume_info_requires_project_access(self):
        task = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        other = APIClient()
        other.force_authenticate(User.objects.get(username="testuser2"))
        denied = (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
        self.assertIn(other.get(self.url(task)).status_code, denied)
        self.assertIn(other.post(self.url(task), {"rerun_from": "odm_dem"}, format="json").status_code, denied)
        task.refresh_from_db()
        self.assertIsNone(task.pending_action)

    def test_replace_mode_sets_rerun_from_and_restart(self):
        task = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        task.options = OPTIONS + [{"name": "rerun-from", "value": "dataset"}]
        task.save()
        with patch("app.api.tasks.worker_tasks.process_task.delay") as delay:
            res = self.client.post(self.url(task), {"rerun_from": "odm_dem"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        delay.assert_called_once()
        task.refresh_from_db()
        self.assertEqual(task.pending_action, pending_actions.RESTART)
        self.assertEqual([o["value"] for o in task.options if o["name"] == "rerun-from"], ["odm_dem"])
        self.assertEqual(len(task.options), len(OPTIONS) + 1)

    def test_version_mode_sets_resume(self):
        root = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        version = root.duplicate(as_version=True)
        with patch("app.api.tasks.worker_tasks.process_task.delay"):
            res = self.client.post(self.url(version), {"rerun_from": "odm_dem", "resume_class": "dem",
                                                       "parent_task": str(root.id)}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        version.refresh_from_db()
        self.assertEqual(version.pending_action, pending_actions.RESUME)
        self.assertEqual(version.resume_info, {"requested_stage": "odm_dem", "resume_class": "dem"})
        self.assertEqual([o["value"] for o in version.options if o["name"] == "rerun-from"], ["odm_dem"])

    def test_resume_post_invalidates_cached_lookup(self):
        task = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        with patch.object(ProcessingNode, "get_task_resume_info", return_value={"resumable": True}) as lookup:
            self.client.get(self.url(task))
            with patch("app.api.tasks.worker_tasks.process_task.delay"):
                self.client.post(self.url(task), {"rerun_from": "odm_dem"}, format="json")
            self.client.get(self.url(task))
            self.assertEqual(lookup.call_count, 2)

    def test_resume_post_rejections(self):
        root = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        version = root.duplicate(as_version=True)
        with patch("app.api.tasks.worker_tasks.process_task.delay"):
            res = self.client.post(self.url(version), {"parent_task": str(version.id)}, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

            # No node task and no parent checkpoint: nothing to resume from
            lone = self.make_task(processing_node=self.node)
            res = self.client.post(self.url(lone), {}, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        lone.refresh_from_db()
        self.assertIsNone(lone.pending_action)


class TestResumeProcessing(VersionTestCase):
    def setUp(self):
        super().setUp()
        self.node = self.make_node()
        root = self.make_task(uuid=NODE_UUID, processing_node=self.node)
        self.version = root.duplicate(as_version=True)
        self.version.options = OPTIONS + [{"name": "rerun-from", "value": "odm_dem"}]
        self.version.pending_action = pending_actions.RESUME
        self.version.resume_info = {"requested_stage": "odm_dem", "resume_class": None}
        self.version.save()

    def process(self, **resume_kwargs):
        with patch.object(ProcessingNode, "is_online", return_value=True), \
                patch.object(ProcessingNode, "resume_task", **resume_kwargs) as resume:
            self.version.process()
        return resume

    def test_resume_stores_the_minted_uuid_and_resume_info(self):
        resume = self.process(return_value={"uuid": NEW_UUID, "resumedFromStage": "odm_dem",
                                            "resumeMode": "resume", "checkpointEngineVersion": "3.5.6"})
        resume.assert_called_once_with(NODE_UUID, self.version.options, new_version=True, jwt_token=None)
        self.version.refresh_from_db()
        self.assertEqual(self.version.uuid, NEW_UUID)
        self.assertEqual(self.version.status, status_codes.QUEUED)
        self.assertIsNone(self.version.pending_action)
        self.assertEqual(self.version.resume_info, {
            "requested_stage": "odm_dem", "resume_class": None, "checkpoint_uuid": NODE_UUID,
            "resumed_from_stage": "odm_dem", "resume_mode": "resume", "checkpoint_engine_version": "3.5.6"})
        # The parent's node task is not touched
        self.assertEqual(self.version.parent_task_uuid, NODE_UUID)

    def test_resume_falls_back_to_requested_stage_when_node_omits_it(self):
        self.process(return_value={"uuid": NEW_UUID})
        self.version.refresh_from_db()
        self.assertEqual(self.version.resume_info["resumed_from_stage"], "odm_dem")
        self.assertEqual(self.version.resume_info["resume_mode"], "resume")

    def test_failed_resume_shows_the_node_error_without_fallback(self):
        self.process(side_effect=NodeResponseError("Resume failed: checkpoint expired"))
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, status_codes.FAILED)
        self.assertEqual(self.version.last_error, "Resume failed: checkpoint expired")
        self.assertEqual(self.version.uuid, "")
        self.assertIsNone(self.version.pending_action)

    def test_connection_error_retries_on_next_tick(self):
        self.process(side_effect=NodeConnectionError("node unreachable"))
        self.version.refresh_from_db()
        self.assertEqual(self.version.pending_action, pending_actions.RESUME)
        self.assertNotEqual(self.version.status, status_codes.FAILED)
        self.assertEqual(self.version.uuid, "")

    def test_expired_tapis_session_gets_the_restart_message(self):
        self.process(side_effect=NodeResponseError("Your session has expired"))
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, status_codes.FAILED)
        self.assertIn("Please refresh the page", self.version.last_error)

    def test_missing_uuid_in_answer_fails(self):
        self.process(return_value={})
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, status_codes.FAILED)
        self.assertEqual(self.version.uuid, "")

    def test_terminal_run_record_carries_resume_columns(self):
        self.process(return_value={"uuid": NEW_UUID, "resumedFromStage": "odm_dem",
                                   "resumeMode": "resume", "checkpointEngineVersion": "3.5.6"})
        self.version.refresh_from_db()
        self.version.status = status_codes.COMPLETED
        run = TaskRun.record_from(self.version)
        self.assertEqual(run.task_uuid, NEW_UUID)
        self.assertEqual(run.version, 2)
        self.assertEqual(run.parent_task_name, "Mapping")
        self.assertEqual(run.parent_task_uuid, NODE_UUID)
        self.assertEqual(run.parent_task_ref, self.version.parent_task_ref)
        self.assertEqual(run.parent_options, OPTIONS)
        self.assertTrue(run.images_from_parent)
        self.assertEqual(run.checkpoint_uuid, NODE_UUID)
        self.assertEqual(run.resumed_from_stage, "odm_dem")
        self.assertEqual(run.checkpoint_engine_version, "3.5.6")
        self.assertEqual(run.resume_mode, "resume")


class TestNodeResumeClient(VersionTestCase):
    class Response:
        def __init__(self, status_code, body):
            self.status_code, self.body = status_code, body

        def json(self):
            if self.body is None:
                raise ValueError("no json")
            return self.body

    def test_get_resume_info_never_raises(self):
        node = self.make_node()
        with patch("nodeodm.models.requests.get", return_value=self.Response(200, {"resumable": True})) as get:
            self.assertEqual(node.get_task_resume_info(NODE_UUID, "jwt"), {"resumable": True})
            self.assertTrue(get.call_args[0][0].endswith("/task/{}/resume".format(NODE_UUID)))
            self.assertEqual(get.call_args[1]["params"], {"token": "jwt"})
        with patch("nodeodm.models.requests.get", return_value=self.Response(404, None)):
            self.assertIsNone(node.get_task_resume_info(NODE_UUID))
        with patch("nodeodm.models.requests.get", side_effect=Exception("boom")):
            self.assertIsNone(node.get_task_resume_info(NODE_UUID))

    def test_resume_task_posts_and_raises_node_message(self):
        node = self.make_node()
        with patch("nodeodm.models.requests.post", return_value=self.Response(200, {"uuid": NEW_UUID})) as post:
            self.assertEqual(node.resume_task(NODE_UUID, OPTIONS, new_version=True, jwt_token="jwt"), {"uuid": NEW_UUID})
            payload = post.call_args[1]["json"]
            self.assertEqual((payload["uuid"], payload["newVersion"]), (NODE_UUID, True))
            self.assertIn("pc-quality", payload["options"])
            self.assertTrue(post.call_args[0][0].endswith("/task/resume"))
            self.assertNotIn("jwt", post.call_args[0][0])
            self.assertEqual(post.call_args[1]["params"], {"token": "jwt"})

        for code, body in ((409, {"errorMessage": "Resume failed: expired"}), (200, {"error": "Resume failed: expired"})):
            with patch("nodeodm.models.requests.post", return_value=self.Response(code, body)):
                with self.assertRaisesRegex(NodeResponseError, "Resume failed: expired"):
                    node.resume_task(NODE_UUID, OPTIONS, new_version=True)

        with patch("nodeodm.models.requests.post", return_value=self.Response(502, None)):
            with self.assertRaisesRegex(NodeResponseError, "HTTP 502"):
                node.resume_task(NODE_UUID, OPTIONS, new_version=True)

    def test_node_errors_do_not_leak_the_token(self):
        node = self.make_node()
        secret = "eyJsecret.jwt.value"
        leaky = requests.exceptions.ConnectionError(
            "HTTPConnectionPool(host='node', port=3000): Max retries exceeded with url: "
            "/task/x/resume?token={} (Caused by NewConnectionError('boom'))".format(secret))

        with patch("nodeodm.models.requests.get", side_effect=leaky):
            with self.assertLogs("app.logger", level="INFO") as logs:
                self.assertIsNone(node.get_task_resume_info(NODE_UUID, secret))
        self.assertFalse(any(secret in line for line in logs.output))
        self.assertTrue(any("[REDACTED]" in line for line in logs.output))

        with patch("nodeodm.models.requests.post", side_effect=leaky):
            with self.assertRaises(NodeConnectionError) as ctx:
                node.resume_task(NODE_UUID, OPTIONS, new_version=True, jwt_token=secret)
        self.assertNotIn(secret, str(ctx.exception))
        self.assertIn("[REDACTED]", str(ctx.exception))
