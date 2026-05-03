"""Pytest fixtures: in-memory SQLite, swap engine before importing app code."""

import os
import tempfile

import pytest

# Set DATABASE_URL to a tmp sqlite file BEFORE importing anything that touches the engine.
_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".sqlite")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db_path}"


@pytest.fixture(autouse=True)
def _reset_db():
    from devsecops_job_hub.db import engine, init_db
    from sqlmodel import SQLModel

    SQLModel.metadata.drop_all(engine)
    init_db()
    yield


def _slim_response_body(response: dict) -> dict:
    # Lever's `mode=json` returns full HTML descriptions per posting (megabytes).
    # The adapter doesn't read description fields — strip them so cassettes stay
    # small enough to commit. Greenhouse responses pass through untouched.
    import json

    body = response.get("body", {})
    raw = body.get("string")
    if not raw:
        return response
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return response
    if not isinstance(payload, list):
        return response
    # Anything the adapters don't actually parse. Slice 3 will add salaryRange
    # parsing — re-record cassettes then by removing it from this set.
    heavy_keys = {
        "description",
        "descriptionPlain",
        "descriptionBody",
        "descriptionBodyPlain",
        "opening",
        "openingPlain",
        "lists",
        "additional",
        "additionalPlain",
        "salaryRange",
    }
    for posting in payload:
        if isinstance(posting, dict):
            for k in heavy_keys:
                posting.pop(k, None)
    body["string"] = json.dumps(payload).encode() if isinstance(raw, bytes) else json.dumps(payload)
    return response


@pytest.fixture(scope="module")
def vcr_config():
    # Public unauthenticated endpoints, but scrub anyway so a future header
    # (auth token, cookie, custom UA leaking machine info) never lands in git.
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("cookie", "REDACTED"),
            ("set-cookie", "REDACTED"),
            ("user-agent", "devsecops-job-hub-test"),
        ],
        "record_mode": "once",
        "before_record_response": _slim_response_body,
    }


def pytest_sessionfinish(session, exitstatus):
    try:
        os.close(_tmp_db_fd)
        os.remove(_tmp_db_path)
    except OSError:
        pass
