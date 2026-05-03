"""Optional OpenTelemetry instrumentation.

Enable with `OTEL_ENABLED=true` in `.env`. Wires three auto-instrumentors:
  - FastAPI: every HTTP request becomes a root span with method, route,
    status, duration, user-agent.
  - SQLAlchemy: every query under the SQLModel engine becomes a child span
    with the SQL statement (parameters scrubbed by default).
  - httpx: every outbound call (Greenhouse, Lever, EDGAR) becomes a child
    span with method, URL, status, duration. Tenacity retries appear as
    sibling spans under the same operation.

Default exporter is the console exporter — span trees print to stdout when
the BatchSpanProcessor flushes (every few seconds and on shutdown). To send
to a real backend (Honeycomb, Tempo, Jaeger, AWS X-Ray, Datadog, etc.) swap
ConsoleSpanExporter for an OTLP exporter; the instrumentation calls don't
change.

Imports are intentionally lazy. When OTEL_ENABLED is False (default — the
test path) the OTel packages are never imported, keeping pytest startup
fast.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_initialized = False


def init_telemetry(app: FastAPI, engine: Engine, service_name: str) -> None:
    """Idempotent. Calling more than once is a no-op so reload-style dev
    servers don't double-instrument."""
    global _initialized
    if _initialized:
        return

    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()

    _initialized = True
    logger.info(
        "OpenTelemetry initialized: service=%s exporter=console (set OTEL_ENABLED=false to disable)",
        service_name,
    )
