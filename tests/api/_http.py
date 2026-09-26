"""Bearer-authenticated JSON requests for the ``tests/api`` full-app suites.

Seven files had grown identical ``_post_json``/``_get_json`` (or
``_post``/``_get``) copies (issue #706). A plain module, not a fixture: each
caller already holds the Flask test ``client`` and its session id.
"""

import json


def _auth(session_id):
    return {"Authorization": f"Bearer {session_id}"}


def post_json(client, url, payload, session_id):
    """POST ``payload`` as JSON to ``url`` as the session ``session_id``."""
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        headers=_auth(session_id),
    )


def get_json(client, url, session_id):
    """GET ``url`` as the session ``session_id``."""
    return client.get(url, headers=_auth(session_id))
