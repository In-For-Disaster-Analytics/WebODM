import unittest

from .url_security import redact_query_params, redact_url


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


if __name__ == '__main__':
    unittest.main()
