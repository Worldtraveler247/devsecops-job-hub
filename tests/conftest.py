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


def pytest_sessionfinish(session, exitstatus):
    try:
        os.close(_tmp_db_fd)
        os.remove(_tmp_db_path)
    except OSError:
        pass
