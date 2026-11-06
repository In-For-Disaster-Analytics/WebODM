import csv
import io
import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from PIL import Image

from app.models import Project, Task, TaskRun
from nodeodm import status_codes
from nodeodm.models import ProcessingNode
from .classes import BootTestCase

LOG = {
    "startTime": "2026-01-01T10:00:00.000000",
    "endTime": "2026-01-01T10:10:00.000000",
    "totalTime": 600.0,
    "stages": [
        {"name": "dataset", "startTime": "2026-01-01T10:00:00.000000", "messages": []},
        {"name": "opensfm", "startTime": "2026-01-01T10:01:00.000000", "messages": []},
        {"name": "odm_dem", "startTime": "2026-01-01T10:06:00.000000", "messages": []},
    ],
}

OPTIONS = [
    {"name": "pc-quality", "value": "high"},
    {"name": "fast-orthophoto", "value": "true"},
    {"name": "tapis-queue", "value": "normal"},
    {"name": "tapis-node", "value": "2"},
    {"name": "tapis-max-run-time", "value": 120},
    {"name": "tapis-allocation", "value": "ABC-123"},
]


class TestTaskRun(BootTestCase):
    def setUp(self):
        super().setUp()
        user = User.objects.get(username="testuser")
        self.project = Project.objects.create(owner=user, name="Run records")

    def make_task(self, status, name="Task", **kwargs):
        t = Task.objects.create(project=self.project, name=name, status=status, options=OPTIONS,
                                images_count=3, processing_time=60000, **kwargs)
        os.makedirs(t.task_path(), exist_ok=True)
        return t

    def write_image(self, task):
        Image.new("RGB", (2, 2)).save(task.task_path("a.jpg"))

    def write_log(self, task):
        os.makedirs(task.assets_path(), exist_ok=True)
        with open(task.assets_path("log.json"), "w") as f:
            json.dump(LOG, f)

    def test_completed_run(self):
        t = self.make_task(status_codes.COMPLETED)
        self.write_image(t)
        self.write_log(t)

        run = TaskRun.record_from(t)

        self.assertEqual(TaskRun.objects.count(), 1)
        self.assertEqual(run.status, status_codes.COMPLETED)
        self.assertEqual(run.task_name, "Task")
        self.assertEqual(run.project_id, self.project.id)
        self.assertEqual((run.image_width, run.image_height), (2, 2))
        self.assertEqual(run.pc_quality, "high")
        self.assertIs(run.fast_orthophoto, True)
        self.assertEqual(run.queue, "normal")
        self.assertEqual(run.nodes, 2)
        self.assertEqual(run.requested_minutes, 120)
        self.assertEqual(run.allocation, "ABC-123")
        self.assertIsNone(run.split)
        self.assertEqual(run.processing_time_ms, 60000)
        self.assertEqual((run.finished_at - run.started_at).total_seconds(), 60)
        self.assertEqual(run.odm_total_seconds, 600.0)
        self.assertEqual(run.stage_seconds, {"dataset": 60, "opensfm": 300, "odm_dem": 240})
        self.assertAlmostEqual(sum(run.stage_seconds.values()), run.odm_total_seconds, delta=1)

    def test_failed_and_canceled_runs(self):
        for status in (status_codes.FAILED, status_codes.CANCELED):
            t = self.make_task(status, name=str(status), last_error="x" * 500)
            self.write_log(t)  # ignored for non-completed tasks
            run = TaskRun.record_from(t)
            self.assertEqual(run.status, status)
            self.assertIsNone(run.stage_seconds)
            self.assertIsNone(run.odm_total_seconds)
            self.assertEqual(len(run.last_error), 300)

    def test_duplicate_guard_and_restart(self):
        t = self.make_task(status_codes.COMPLETED)
        TaskRun.record_from(t)
        self.assertIsNone(TaskRun.record_from(t))
        self.assertEqual(TaskRun.objects.count(), 1)

        # Restarted task that completes again
        t.processing_time = 90000
        TaskRun.record_from(t)
        self.assertEqual(TaskRun.objects.count(), 2)

        # Same state reported again well outside the duplicate window is a new run
        # (e.g. a restart that fails again before any processing time is known).
        last = TaskRun.objects.order_by('-finished_at', '-id').first()
        last.finished_at = last.finished_at - timedelta(minutes=5)
        last.save()
        TaskRun.record_from(t)
        self.assertEqual(TaskRun.objects.count(), 3)

    def test_tapis_job_and_task_uuid_recorded(self):
        t = self.make_task(status_codes.COMPLETED)
        t.uuid = "9ef37fe9-807c-45da-9276-63dc6ee96ab1"
        t.save()
        run = TaskRun.record_from(t, tapis_job={"tapisJobId": "job-123", "jobName": "nodeodx-abc", "state": "done"})
        self.assertEqual(run.task_uuid, t.uuid)
        self.assertEqual(run.tapis_job_id, "job-123")
        self.assertEqual(run.tapis_job_name, "nodeodx-abc")

        # No answer from the node: the keys stay null, the row is still written
        run2 = TaskRun.record_from(t, finished_at=run.finished_at + timedelta(minutes=5), tapis_job=None)
        self.assertIsNone(run2.tapis_job_id)

    def test_lookup_tapis_job_only_for_tapis_nodes(self):
        node = ProcessingNode.objects.create(hostname="node", port=3000, available_options=[{"name": "dsm"}])
        t = self.make_task(status_codes.COMPLETED, processing_node=node)
        t.uuid = "9ef37fe9-807c-45da-9276-63dc6ee96ab1"
        t.save()
        with patch.object(ProcessingNode, 'get_task_tapis_job') as lookup:
            self.assertIsNone(t.lookup_tapis_job())
            lookup.assert_not_called()

        node.available_options = [{"name": "tapis-allocation"}]
        node.save()
        with patch.object(ProcessingNode, 'get_task_tapis_job', return_value={"tapisJobId": "job-1"}) as lookup:
            self.assertEqual(t.lookup_tapis_job(), {"tapisJobId": "job-1"})
            lookup.assert_called_once_with(t.uuid, None)

        # The node client swallows transport and route errors
        with patch.object(ProcessingNode, 'api_client', side_effect=Exception("boom")):
            self.assertIsNone(node.get_task_tapis_job(t.uuid))

    def test_lineage_and_resume_columns_copied(self):
        parent = self.make_task(status_codes.COMPLETED, name="Base")
        t = parent.duplicate(as_version=True)
        t.status = status_codes.COMPLETED
        t.resume_info = {"checkpoint_uuid": "parent-uuid", "resumed_from_stage": "odm_dem",
                         "checkpoint_engine_version": "3.5.6", "resume_mode": "resume"}
        t.save()
        run = TaskRun.record_from(t)
        self.assertEqual((run.version, run.parent_task_ref, run.parent_task_name), (2, parent.id, "Base"))
        self.assertEqual(run.parent_options, OPTIONS)
        self.assertTrue(run.images_from_parent)
        self.assertEqual((run.checkpoint_uuid, run.resumed_from_stage, run.resume_mode, run.checkpoint_engine_version),
                         ("parent-uuid", "odm_dem", "resume", "3.5.6"))

        # A task that is not a version has neutral defaults
        plain = TaskRun.record_from(parent)
        self.assertEqual((plain.version, plain.parent_task_ref, plain.parent_task_name, plain.resume_mode),
                         (1, None, "", None))
        self.assertFalse(plain.images_from_parent)

    def test_unknown_processing_time_is_null(self):
        t = self.make_task(status_codes.FAILED)
        t.processing_time = -1
        t.save()
        run = TaskRun.record_from(t)
        self.assertIsNone(run.processing_time_ms)
        self.assertIsNone(run.started_at)

    def test_log_single_stage_without_end_time(self):
        t = self.make_task(status_codes.COMPLETED)
        os.makedirs(t.assets_path(), exist_ok=True)
        with open(t.assets_path("log.json"), "w") as f:
            json.dump({
                "startTime": "2026-01-01T10:00:00.000000",
                "totalTime": 90.0,
                "stages": [{"name": "dataset", "startTime": "2026-01-01T10:00:00.000000", "messages": []}],
            }, f)
        run = TaskRun.record_from(t)
        self.assertEqual(run.odm_total_seconds, 90.0)
        self.assertEqual(run.stage_seconds, {"dataset": 90.0})

    def test_task_deletion_keeps_run(self):
        t = self.make_task(status_codes.COMPLETED, name="Doomed")
        TaskRun.record_from(t)
        t.delete()
        run = TaskRun.objects.get()
        self.assertIsNone(run.task)
        self.assertEqual(run.task_name, "Doomed")

    def test_node_fields(self):
        node = ProcessingNode.objects.create(hostname="localhost", port=3000, label="Node A",
                                             engine="odm", engine_version="3.5.5")
        t = self.make_task(status_codes.COMPLETED, processing_node=node)
        run = TaskRun.record_from(t)
        self.assertEqual((run.processing_node, run.engine, run.engine_version), ("Node A", "odm", "3.5.5"))

    def test_malformed_log_and_bad_image(self):
        t = self.make_task(status_codes.COMPLETED)
        with open(t.task_path("bad.jpg"), "w") as f:
            f.write("not an image")
        os.makedirs(t.assets_path(), exist_ok=True)
        with open(t.assets_path("log.json"), "w") as f:
            f.write("{")
        run = TaskRun.record_from(t)
        self.assertIsNone(run.stage_seconds)
        self.assertIsNone(run.image_width)

    def test_export_and_backfill(self):
        a = self.make_task(status_codes.COMPLETED, name="A")
        self.write_log(a)
        self.make_task(status_codes.FAILED, name="B")
        self.make_task(status_codes.RUNNING, name="C")
        TaskRun.record_from(a)

        out = io.StringIO()
        call_command("backfillruns", stdout=out)
        self.assertIn("Created: 1", out.getvalue())
        self.assertEqual(TaskRun.objects.count(), 2)

        out = io.StringIO()
        call_command("backfillruns", stdout=out)
        self.assertIn("Created: 0", out.getvalue())
        self.assertEqual(TaskRun.objects.count(), 2)

        out = io.StringIO()
        call_command("exportruns", stdout=out)
        rows = list(csv.reader(io.StringIO(out.getvalue())))
        self.assertEqual(rows[0], [f.attname for f in TaskRun._meta.concrete_fields])
        self.assertEqual(len(rows), 3)
        self.assertEqual(json.loads(rows[1][rows[0].index("options")])[0]["name"], "pc-quality")

        out = io.StringIO()
        call_command("exportruns", status="FAILED", stdout=out)
        self.assertEqual(len(list(csv.reader(io.StringIO(out.getvalue())))), 2)

        out = io.StringIO()
        call_command("exportruns", since="2999-01-01", stdout=out)
        self.assertEqual(len(list(csv.reader(io.StringIO(out.getvalue())))), 1)

    def test_record_failure_is_swallowed(self):
        t = self.make_task(status_codes.COMPLETED)
        with patch.object(TaskRun, "save", side_effect=Exception("boom")):
            with self.assertLogs("app.logger", level="WARNING") as logs:
                self.assertIsNone(TaskRun.record_from(t))
        self.assertIn("boom", logs.output[0])
        t.refresh_from_db()
        self.assertEqual(t.status, status_codes.COMPLETED)
