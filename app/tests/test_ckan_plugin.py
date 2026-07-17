import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from app.models import Project, Task
from app.tests.classes import BootTestCase
from nodeodm import status_codes

from coreplugins.ckan import publisher


# ── Pure unit tests (no DB needed, but BootTestCase is fine) ─────────────────

class TestInferFormat(BootTestCase):
    def test_known_extensions(self):
        self.assertEqual(publisher._infer_format('orthophoto.tif'), 'GTiff')
        self.assertEqual(publisher._infer_format('georeferenced_model.laz'), 'LAZ')
        self.assertEqual(publisher._infer_format('georeferenced_model.las'), 'LAS')
        self.assertEqual(publisher._infer_format('georeferenced_model.ply'), 'PLY')
        self.assertEqual(publisher._infer_format('report.pdf'), 'PDF')
        self.assertEqual(publisher._infer_format('cameras.json'), 'JSON')
        self.assertEqual(publisher._infer_format('all.zip'), 'ZIP')

    def test_unknown_extension(self):
        self.assertEqual(publisher._infer_format('file.xyz'), 'XYZ')

    def test_no_extension(self):
        self.assertEqual(publisher._infer_format('noextension'), 'OTHER')


class TestBuildRemoteResources(BootTestCase):
    def _make_task(self, assets):
        task = MagicMock()
        task.id = 42
        task.project_id = 7
        task.available_assets = assets
        return task

    def _make_request(self, base='https://webodm.example.com'):
        req = MagicMock()
        req.build_absolute_uri.return_value = base + '/'
        return req

    def test_includes_publishable_assets(self):
        task = self._make_task(['orthophoto.tif', 'report.pdf'])
        req = self._make_request()
        resources = publisher.build_remote_resources(task, req)
        urls = [r['url'] for r in resources]
        self.assertIn('https://webodm.example.com/api/projects/7/tasks/42/download/orthophoto.tif', urls)
        self.assertIn('https://webodm.example.com/api/projects/7/tasks/42/download/report.pdf', urls)

    def test_excludes_non_publishable_assets(self):
        task = self._make_task(['cameras.json', 'shots.geojson', 'orthophoto.tif'])
        req = self._make_request()
        resources = publisher.build_remote_resources(task, req)
        names = [r['name'] for r in resources]
        self.assertNotIn('Camera Parameters (JSON)', names)
        self.assertIn('Orthophoto (GeoTIFF)', names)

    def test_always_includes_viewer_links(self):
        task = self._make_task([])
        req = self._make_request()
        resources = publisher.build_remote_resources(task, req)
        formats = [r['format'] for r in resources]
        self.assertIn('HTML', formats)
        urls = [r['url'] for r in resources]
        self.assertTrue(any('/map/' in u for u in urls))
        self.assertTrue(any('/3d/' in u for u in urls))

    def test_correct_format_labels(self):
        task = self._make_task(['orthophoto.tif', 'georeferenced_model.laz'])
        req = self._make_request()
        resources = publisher.build_remote_resources(task, req)
        by_name = {r['name']: r['format'] for r in resources}
        self.assertEqual(by_name['Orthophoto (GeoTIFF)'], 'GTiff')
        self.assertEqual(by_name['Point Cloud (LAZ)'], 'LAZ')


class TestBuildTags(BootTestCase):
    def _make_task(self, assets, stats=None):
        task = MagicMock()
        task.available_assets = assets
        task.assets_path = MagicMock(return_value='/nonexistent/cameras.json')
        task.get_statistics = MagicMock(return_value=stats or {})
        return task

    def test_base_tags_always_present(self):
        task = self._make_task([])
        tags = publisher.build_tags(task)
        for base in ('drone', 'uas', 'sfm', 'webodm'):
            self.assertIn(base, tags)

    def test_orthophoto_tag(self):
        task = self._make_task(['orthophoto.tif'])
        self.assertIn('orthophoto', publisher.build_tags(task))

    def test_point_cloud_tag(self):
        task = self._make_task(['georeferenced_model.laz'])
        self.assertIn('point-cloud', publisher.build_tags(task))

    def test_elevation_tags(self):
        task = self._make_task(['dsm.tif', 'dtm.tif'])
        tags = publisher.build_tags(task)
        self.assertIn('dsm', tags)
        self.assertIn('dtm', tags)
        self.assertIn('elevation', tags)

    def test_gcp_tag(self):
        task = self._make_task([], stats={'spatial_refs': ['gcp']})
        self.assertIn('gcp-controlled', publisher.build_tags(task))

    def test_tags_sorted(self):
        task = self._make_task(['orthophoto.tif', 'dsm.tif'])
        tags = publisher.build_tags(task)
        self.assertEqual(tags, sorted(tags))


# ── View integration tests ────────────────────────────────────────────────────

AGENT_URL = 'https://agent.example.com'


def _make_completed_task(user):
    project = Project.objects.get(owner=user)
    task = Task.objects.create(
        project=project,
        name='Test Task',
        status=status_codes.COMPLETED,
        images_count=10,
    )
    return task


class TestChatStartView(BootTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='testuser')
        self.client.force_authenticate(user=self.user)

    def test_503_when_agent_not_configured(self):
        task = _make_completed_task(self.user)
        with override_settings(WO_DSO_AGENT_URL=''):
            res = self.client.post(f'/api/plugins/ckan/task/{task.id}/chat/start')
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_400_when_task_not_completed(self):
        project = Project.objects.get(owner=self.user)
        task = Task.objects.create(project=project, name='Pending Task',
                                   status=status_codes.RUNNING, images_count=1)
        with override_settings(WO_DSO_AGENT_URL=AGENT_URL):
            with patch('coreplugins.ckan.api_views.publisher.get_user_tapis_jwt',
                       return_value='fake-jwt'):
                res = self.client.post(f'/api/plugins/ckan/task/{task.id}/chat/start')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_403_when_no_tapis_token(self):
        task = _make_completed_task(self.user)
        with override_settings(WO_DSO_AGENT_URL=AGENT_URL):
            with patch('coreplugins.ckan.api_views.publisher.get_user_tapis_jwt',
                       side_effect=RuntimeError('No Tapis token')):
                res = self.client.post(f'/api/plugins/ckan/task/{task.id}/chat/start')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_201_on_success(self):
        task = _make_completed_task(self.user)
        fake_agent_response = {
            'thread_id': 'thread-abc',
            'status': 'completed',
            'result': {'review_markdown': 'Here is the proposed metadata.'},
        }
        with override_settings(WO_DSO_AGENT_URL=AGENT_URL):
            with patch('coreplugins.ckan.api_views.publisher.get_user_tapis_jwt',
                       return_value='fake-jwt'), \
                 patch('coreplugins.ckan.api_views.publisher.build_remote_resources',
                       return_value=[]), \
                 patch('coreplugins.ckan.api_views.publisher.build_dataset',
                       return_value={'title': 'Test'}), \
                 patch('coreplugins.ckan.api_views.requests.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = fake_agent_response
                mock_post.return_value.raise_for_status = MagicMock()
                res = self.client.post(f'/api/plugins/ckan/task/{task.id}/chat/start')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertEqual(data['thread_id'], 'thread-abc')
        self.assertIn('message', data)

    def test_response_includes_timestamp_in_store(self):
        task = _make_completed_task(self.user)
        from app.plugins.data_store import GlobalDataStore
        ds = GlobalDataStore('ckan')

        fake_agent_response = {
            'thread_id': 'thread-ts',
            'status': 'completed',
            'result': {'review_markdown': 'Metadata.'},
        }
        with override_settings(WO_DSO_AGENT_URL=AGENT_URL):
            with patch('coreplugins.ckan.api_views.publisher.get_user_tapis_jwt',
                       return_value='fake-jwt'), \
                 patch('coreplugins.ckan.api_views.publisher.build_remote_resources',
                       return_value=[]), \
                 patch('coreplugins.ckan.api_views.publisher.build_dataset',
                       return_value={'title': 'Test'}), \
                 patch('coreplugins.ckan.api_views.requests.post') as mock_post:
                mock_post.return_value.json.return_value = fake_agent_response
                mock_post.return_value.raise_for_status = MagicMock()
                self.client.post(f'/api/plugins/ckan/task/{task.id}/chat/start')

        record = ds.get_json(f'task_{task.id}_ckan_publish', {})
        self.assertIn('timestamp', record)
        self.assertRegex(record['timestamp'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')


class TestChatConfirmView(BootTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='testuser')
        self.client.force_authenticate(user=self.user)

    def test_400_when_no_thread_id(self):
        task = _make_completed_task(self.user)
        with override_settings(WO_DSO_AGENT_URL=AGENT_URL):
            res = self.client.post(f'/api/plugins/ckan/task/{task.id}/chat/confirm',
                                   data={}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_202_queues_celery_task(self):
        task = _make_completed_task(self.user)
        with override_settings(WO_DSO_AGENT_URL=AGENT_URL):
            with patch('coreplugins.ckan.api_views.run_function_async') as mock_async:
                res = self.client.post(
                    f'/api/plugins/ckan/task/{task.id}/chat/confirm',
                    data={'thread_id': 'thread-abc'},
                    format='json',
                )
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        mock_async.assert_called_once()

    def test_confirm_sets_timestamp_in_store(self):
        task = _make_completed_task(self.user)
        from app.plugins.data_store import GlobalDataStore
        ds = GlobalDataStore('ckan')

        with override_settings(WO_DSO_AGENT_URL=AGENT_URL):
            with patch('coreplugins.ckan.api_views.run_function_async'):
                self.client.post(
                    f'/api/plugins/ckan/task/{task.id}/chat/confirm',
                    data={'thread_id': 'thread-abc'},
                    format='json',
                )

        record = ds.get_json(f'task_{task.id}_ckan_publish', {})
        self.assertIn('timestamp', record)


class TestPublishStatusView(BootTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='testuser')
        self.client.force_authenticate(user=self.user)

    def test_returns_idle_when_no_store_record(self):
        task = _make_completed_task(self.user)
        res = self.client.get(f'/api/plugins/ckan/task/{task.id}/publish-status')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn('status', data)

    def test_returns_ckan_url_from_task_field(self):
        project = Project.objects.get(owner=self.user)
        task = Task.objects.create(
            project=project,
            name='Published Task',
            status=status_codes.COMPLETED,
            images_count=1,
            ckan_url='https://ckan.tacc.utexas.edu/dataset/test-dataset',
        )
        res = self.client.get(f'/api/plugins/ckan/task/{task.id}/publish-status')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()['ckan_url'],
                         'https://ckan.tacc.utexas.edu/dataset/test-dataset')


class TestCkanUrlReadOnly(BootTestCase):
    """ckan_url must not be writable via the task PATCH endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.get(username='testuser')
        self.client.force_authenticate(user=self.user)

    def test_ckan_url_ignored_on_patch(self):
        project = Project.objects.get(owner=self.user)
        task = Task.objects.create(
            project=project,
            name='Patch Test Task',
            status=status_codes.COMPLETED,
            images_count=1,
        )
        res = self.client.patch(
            f'/api/projects/{project.id}/tasks/{task.id}/',
            data={'ckan_url': 'https://attacker.com/fake'},
            format='json',
        )
        task.refresh_from_db()
        self.assertNotEqual(task.ckan_url, 'https://attacker.com/fake')
