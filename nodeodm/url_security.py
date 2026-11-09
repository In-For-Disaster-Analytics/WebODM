import re
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


# A JWT is three base64url segments, the first two starting with the encoded '{"'.
_JWT_PATTERN = re.compile(r'eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*')
_TOKEN_PARAM_PATTERN = re.compile(r"((?:access_)?token['\"]?\s*[=:]\s*['\"]?)[^&'\"\s,}]+", re.IGNORECASE)


def redact_text(value):
    """
    Mask bearer credentials in free text before logging it.

    Task options and ClusterODM responses carry the user's Tapis JWT, both as a bare
    token and inside ``?token=`` query strings (the ``sm-cluster`` option URL), so dumps
    of response bodies must pass through here.
    """
    text = _JWT_PATTERN.sub('[REDACTED]', str(value))
    return _TOKEN_PARAM_PATTERN.sub(r'\1[REDACTED]', text)
