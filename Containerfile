# syntax=docker/dockerfile:1.7
# Multi-stage Containerfile for the DevSecOps Job Hub.
# Build:   podman build -t devsecops-job-hub:dev .
# Run:     podman run --rm -p 8000:8000 --env-file .env devsecops-job-hub:dev
#
# Two-stage layout keeps the runtime image small (~200MB) by leaving build
# tooling (gcc, headers) in the throwaway builder layer. Runs as a non-root
# user; HEALTHCHECK probes /healthz so the orchestrator can detect bad pods.

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

# `--prefix=/install` lets us copy a clean tree of installed packages to the
# runtime stage without dragging /var/lib/apt/lists or pip caches along.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install .


FROM python:3.12-slim AS runtime

# Non-root user. -m gives /home/app for any tmp scratch space the framework
# needs; -s /sbin/nologin disables interactive logins inside the container.
RUN groupadd -r app \
 && useradd -r -g app -m -d /home/app -s /sbin/nologin app

# Copy the installed package + its dependencies from the builder stage.
COPY --from=builder /install /usr/local

WORKDIR /app

USER app

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Probe the FastAPI healthz endpoint. Uses stdlib so we don't add curl just
# for healthchecks. Status 200 = healthy; anything else = unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://localhost:8000/healthz', timeout=3); sys.exit(0 if r.status==200 else 1)"

ENTRYPOINT ["uvicorn", "devsecops_job_hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
