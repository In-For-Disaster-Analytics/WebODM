import unittest

from .url_security import redact_query_params, redact_text, redact_url


class JWTNodeWrapperSecurityTests(unittest.TestCase):
    def test_redacts_token_query_parameter(self):
        token = 'eyJheader.payload.signature'
        safe_url = redact_url('https://cluster.example/task/new?token=' + token + '&line=3')

        self.assertNotIn(token, safe_url)
        self.assertIn('token=%5BREDACTED%5D', safe_url)
        self.assertIn('line=3', safe_url)

    def test_redacts_sensitive_logged_parameters(self):
        token = 'secret-token'
        safe_params = redact_query_params({'token': token, 'line': 4})

        self.assertEqual(safe_params['token'], '[REDACTED]')
        self.assertEqual(safe_params['line'], 4)

    def test_redact_text_masks_jwts_and_token_params_in_task_dumps(self):
        jwt = 'eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.c2lnLXBhcnRfMQ'
        dump = ("{'options': [{'name': 'sm-cluster', 'value': 'https://clusterodm.example/?token=%s'}, "
                "{'name': 'tapis-queue', 'value': 'normal'}]} Authorization: Bearer %s") % (jwt, jwt)

        safe = redact_text(dump)

        self.assertNotIn(jwt, safe)
        self.assertNotIn('eyJ', safe)
        self.assertIn('token=[REDACTED]', safe)
        self.assertIn("'tapis-queue', 'value': 'normal'", safe)

    def test_redact_text_masks_token_fields_in_json_and_dicts(self):
        self.assertNotIn('abc123', redact_text('{"token": "abc123", "line": 3}'))
        self.assertNotIn('abc123', redact_text("{'access_token': 'abc123'}"))
        self.assertIn('line', redact_text('{"token": "abc123", "line": 3}'))

    def test_redact_text_leaves_ordinary_text_alone(self):
        text = 'JOBS_TRANSFER_INCOMPLETE Transfer 4980d18b-923c-4387-8acc-f8f6f2321c6'
        self.assertEqual(redact_text(text), text)


if __name__ == '__main__':
    unittest.main()
