import unittest
from unittest import mock

from pyodx.exceptions import NodeServerError

from .jwt_node_wrapper import JWTNodeWrapper


def _json_response(payload, status_code=200):
    response = mock.Mock()
    response.status_code = status_code
    response.headers = {'content-type': 'application/json'}
    response.json.return_value = payload
    response.text = str(payload)
    response.content = response.text.encode('utf-8')
    return response


class JWTNodeWrapperRestartTests(unittest.TestCase):
    """ClusterODM answers HTTP 200 with {"error": ...} when it cannot restart a task,
    for example when the task is only a canceled placeholder with no node behind it.
    The wrapper must raise, like pyodm does, so the worker resubmits the task instead of
    reading the stale canceled status back as the result of the restart."""

    UUID = '2e322b13-5382-457c-a82d-9e36b145d201'
    INFO = {'uuid': UUID, 'status': {'code': 50}, 'options': [], 'output': []}

    def setUp(self):
        self.wrapper = JWTNodeWrapper('cluster.example', 443, '', 30, 'header.payload.signature')

    @mock.patch('nodeodm.jwt_node_wrapper.requests.post')
    @mock.patch('nodeodm.jwt_node_wrapper.requests.get')
    def test_restart_raises_on_error_body(self, get, post):
        get.return_value = _json_response(self.INFO)
        post.return_value = _json_response({'error': 'Action not supported. Please create a new task.'})

        task = self.wrapper.get_task(self.UUID)
        with self.assertRaises(NodeServerError) as raised:
            task.restart({'dsm': True})

        self.assertIn('Action not supported', str(raised.exception))
        self.assertEqual(post.call_args.kwargs['json']['uuid'], self.UUID)

    @mock.patch('nodeodm.jwt_node_wrapper.requests.post')
    @mock.patch('nodeodm.jwt_node_wrapper.requests.get')
    def test_restart_returns_body_on_success(self, get, post):
        get.return_value = _json_response(self.INFO)
        post.return_value = _json_response({'success': True})

        task = self.wrapper.get_task(self.UUID)

        self.assertEqual(task.restart(), {'success': True})

    @mock.patch('nodeodm.jwt_node_wrapper.requests.post')
    @mock.patch('nodeodm.jwt_node_wrapper.requests.get')
    def test_restart_raises_on_http_error(self, get, post):
        get.return_value = _json_response(self.INFO)
        post.return_value = _json_response({'error': 'boom'}, status_code=500)

        task = self.wrapper.get_task(self.UUID)
        with self.assertRaises(Exception):
            task.restart()


if __name__ == '__main__':
    unittest.main()
