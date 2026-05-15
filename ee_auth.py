"""Earth Engine authentication helper.

Service-account-only initialization for unattended deployments (Hugging Face
Spaces, GitHub Actions, local dev). Reads a service account JSON from the
environment and configures Earth Engine via ``ee.ServiceAccountCredentials``.

Environment variables
---------------------
GCP_SERVICE_ACCOUNT_JSON
    Full JSON string of a Google Cloud service account key. Required.
EE_PROJECT_ID
    GCP project id for ``ee.Initialize(project=...)``. Optional; defaults to
    the ``project_id`` field inside the service account JSON.

See ``.agent/agent.md`` (sections 4.2 and 4.3) and ``README.md`` for setup.
"""

from __future__ import annotations

import json
import os
import tempfile

import ee
import streamlit as st


_MISSING_SECRET_MESSAGE = (
    "Earth Engine is not configured. Set the `GCP_SERVICE_ACCOUNT_JSON` "
    "environment variable (Hugging Face Space secret or local `.env`) to the "
    "full JSON of a Google Cloud service account key. See README.md for the "
    "one-time GCP setup."
)


def _load_secret() -> tuple[dict, str]:
    sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError(_MISSING_SECRET_MESSAGE)

    try:
        info = json.loads(sa_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "GCP_SERVICE_ACCOUNT_JSON is set but is not valid JSON. Paste the "
            "entire downloaded key file contents into the secret."
        ) from exc

    project = os.environ.get("EE_PROJECT_ID") or info.get("project_id")
    if not project:
        raise RuntimeError(
            "Could not determine GCP project id. Set EE_PROJECT_ID or include "
            "`project_id` in the service account JSON."
        )

    if "client_email" not in info:
        raise RuntimeError(
            "Service account JSON is missing `client_email`. Re-download the "
            "key from IAM & Admin > Service accounts > Keys."
        )

    return info, project


@st.cache_resource(show_spinner=False)
def init_earth_engine() -> str:
    """Initialize Earth Engine with a service-account credential.

    Idempotent across Streamlit reruns thanks to ``@st.cache_resource``.
    Returns the GCP project id used for initialization.
    """
    info, project = _load_secret()

    fd, key_path = tempfile.mkstemp(suffix=".json", prefix="ee_sa_")
    os.chmod(key_path, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(info))
        credentials = ee.ServiceAccountCredentials(info["client_email"], key_path)
        ee.Initialize(credentials, project=project)
    finally:
        try:
            os.remove(key_path)
        except OSError:
            pass

    return project


__all__ = ["init_earth_engine"]
