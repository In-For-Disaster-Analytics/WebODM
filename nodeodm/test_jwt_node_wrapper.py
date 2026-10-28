"""Offline consumer contracts for the established ClusterODX backend."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from pyodx.exceptions import NodeServerError
from .jwt_node_wrapper import JWTNodeWrapper


class JWTNodeWrapperContractTests(unittest.TestCase):
    def setUp(self):
        self.client = JWTNodeWrapper('cluster.example', 443, 'node-token', 30, 'user-token')

    @patch('nodeodm.jwt_node_wrapper.requests.post')
    def test_shared_path_submission_preserves_user_and_options(self, post):
        post.return_value = Mock(status_code=200, headers={'content-type': 'application/json'}, content=b'{}', json=lambda: {'uuid': 'remote-id'})
        with self.assertLogs('app.logger', level='INFO') as logs:
            result = self.client.create_task_from_path('/shared/project/task/images', {'tapis-allocation': 'allocation'}, 'Flight')
        self.assertEqual(result.uuid, 'remote-id')
        args, kwargs = post.call_args
        self.assertEqual(urlsplit(args[0]).scheme, 'https')
        self.assertEqual(parse_qs(urlsplit(args[0]).query), {'token': ['user-token']})
        self.assertEqual(kwargs['data']['import_path'], '/shared/project/task/images')
        self.assertEqual(json.loads(kwargs['data']['options']), [{'name': 'tapis-allocation', 'value': 'allocation'}])
        self.assertNotIn('user-token', '\n'.join(logs.output))

    @patch('nodeodm.jwt_node_wrapper.requests.get')
    def test_status_uses_pyodx_task_info_and_preserves_output(self, get):
        get.return_value = Mock(status_code=200, headers={'content-type': 'application/json'}, content=b'{}', json=lambda: {
            'uuid': 'remote-id', 'name': 'Flight', 'dateCreated': 0,
            'processingTime': 1000, 'status': {'code': 20},
            'options': [], 'imagesCount': 2, 'progress': 10,
            'output': ['working'],
        })
        info = self.client.get_task('remote-id').info(0)
        self.assertEqual(info.uuid, 'remote-id')
        self.assertEqual(info.output, ['working'])
        self.assertEqual(info.images_count, 2)

    @patch('nodeodm.jwt_node_wrapper.requests.post')
    def test_node_token_fallback_without_user_token(self, post):
        post.return_value = Mock(status_code=200, headers={'content-type': 'application/json'}, content=b'{}', json=lambda: {'uuid': 'remote-id'})
        client = JWTNodeWrapper('cluster.example', 443, 'node-token', 30, None)
        client.create_task_from_path('/shared/images', {})
        self.assertEqual(parse_qs(urlsplit(post.call_args[0][0]).query), {'token': ['node-token']})

    @patch('nodeodm.jwt_node_wrapper.requests.post')
    def test_multipart_upload_retains_option_contract(self, post):
        response = Mock(status_code=200, headers={'content-type': 'application/json'}, content=b'{}')
        response.json.return_value = {'uuid': 'remote-id'}
        post.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'image.jpg'
            image.write_bytes(b'image')
            task = self.client.create_task([str(image)], {'dsm': True}, 'Flight')
        self.assertEqual(task.uuid, 'remote-id')
        self.assertEqual(json.loads(post.call_args.kwargs['data']['options']), [{'name': 'dsm', 'value': True}])
        self.assertTrue(post.call_args.kwargs['files'][0][1].closed)

    @patch('nodeodm.jwt_node_wrapper.requests.get')
    def test_missing_remote_uuid_rejects_status(self, get):
        get.return_value = Mock(status_code=200, headers={'content-type': 'application/json'}, content=b'{}', json=lambda: {'name': 'missing-id'})
        with self.assertRaises(NodeServerError):
            self.client._fetch_task_info('remote-id')

    @patch('nodeodm.jwt_node_wrapper.JWTNodeWrapper._fetch_task_info')
    @patch('nodeodm.jwt_node_wrapper.requests.post')
    def test_restart_cancel_and_remove_keep_user_auth(self, post, fetch):
        fetch.return_value = {'uuid': 'remote-id'}
        post.return_value = Mock(status_code=200, headers={}, content=b'{}', json=lambda: {'success': True})
        task = self.client.get_task('remote-id')
        for method, path in [(task.restart, '/task/restart'), (task.cancel, '/task/cancel'), (task.remove, '/task/remove')]:
            with self.subTest(path=path):
                self.assertTrue(method()['success'])
                args, kwargs = post.call_args
                self.assertEqual(urlsplit(args[0]).path, path)
                self.assertEqual(parse_qs(urlsplit(args[0]).query), {'token': ['user-token']})
                self.assertEqual(kwargs['json']['uuid'], 'remote-id')


if __name__ == '__main__':
    unittest.main()
