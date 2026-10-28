from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_QUERY_KEYS = {'token', 'access_token', 'authorization'}


def redact_query_params(params):
    """Return query parameters safe to include in logs."""
    return {
        key: '[REDACTED]' if str(key).lower() in _SENSITIVE_QUERY_KEYS else value
        for key, value in params.items()
    }


def redact_url(endpoint):
    """Remove bearer credentials from a URL before logging it."""
    parts = urlsplit(endpoint)
    query = [
        (key, '[REDACTED]' if key.lower() in _SENSITIVE_QUERY_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
