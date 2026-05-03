# DevSecOps Job Hub

A web app that helps cleared and clearable candidates find DevSecOps, cloud security, and adjacent engineering roles at U.S. government contractors and defense-tech companies.

This is **Slice 1 of 4**. It proves the end-to-end pipeline: company seed → ATS adapter → DB → filterable Jinja UI. Slices 2–4 add more sources, salary enrichment, and cloud deploy.

---

## Tech stack

- **Python 3.12** + **FastAPI** (server-rendered, no SPA)
- **SQLModel** on **SQLite** for dev (Postgres in prod, Slice 4)
- **httpx** (async) for ATS API calls, **tenacity** for retry
- **Jinja2** templates + plain CSS, styled to match the App Hub aesthetic

## Quick start

```bash
# 1. Create venv and install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Run tests
pytest

# 3. Start the dev server
uvicorn devsecops_job_hub.main:app --reload

# 4. In a separate terminal, pull live job postings
curl -X POST http://127.0.0.1:8000/admin/refresh

# 5. Open http://127.0.0.1:8000/
```

## Project structure

```
src/devsecops_job_hub/
├── main.py              # FastAPI app, routes, lifespan (init_db + seed)
├── config.py            # Pydantic settings (env-driven)
├── db.py                # SQLModel engine + session
├── models.py            # Company, Job, all enums
├── classify.py          # Heuristic title→role/clearance/stage classifiers
├── adapters/
│   ├── base.py          # ATSAdapter Protocol
│   └── greenhouse.py    # Greenhouse public boards API client
├── services/
│   └── refresh.py       # Pull from adapters, idempotent upsert, soft-delete stale
├── seed/
│   └── companies.py     # Hand-curated initial company list
├── templates/           # Jinja templates (base + jobs page)
└── static/              # CSS

tests/
├── conftest.py                # tmp SQLite per test run
├── test_classify.py           # Pure unit tests on classifier
├── test_greenhouse_adapter.py # Adapter test using httpx.MockTransport + JSON fixture
├── test_app.py                # FastAPI smoke tests
└── fixtures/greenhouse_sample.json
```

---

## Tooling — what's in and what's deferred

This project deliberately starts with a small set of tools and adds rigor in later slices. Below is what each tool does, why it matters, and when it'll be added.

### In place from day 1

| Tool | What it does | Why it's worth having from day 1 |
|---|---|---|
| **ruff** | Linter + formatter for Python (replaces flake8/black/isort). Runs in milliseconds. | Catches obvious bugs and enforces consistent style on every save. |
| **pytest** | The standard Python test framework. | You don't ship code without tests. Fixtures + parametrize + plugins make it the default. |
| **mypy** (non-strict) | Static type checker. Reads your type hints and flags type mismatches before runtime. | Annotated APIs catch a class of bugs the linter can't. Non-strict means "annotate as you go" — enforcement comes in Slice 4. |
| **bandit** | Security-focused linter for Python. Flags `eval()`, hardcoded passwords, weak crypto, SQL-injection patterns. | Cheap SAST with low false-positive rate. Fits the spec's security-first posture. |
| **gitleaks** | Pre-commit hook that scans the diff for accidentally committed secrets (AWS keys, GitHub tokens, etc.). Blocks the commit if it finds one. | Committed secrets are *painful* to remove from git history. Worth having from commit #1. |
| **pre-commit** | Runs the above hooks automatically before each commit. | Makes the safety net invisible — you don't have to remember. |

### Deferred (added in later slices)

| Tool | What it does | When we'll add it |
|---|---|---|
| **vcrpy** | Records real HTTP responses to YAML files on first test run, replays them on subsequent runs. Makes adapter tests fast and offline. | **Slice 2** — once the Lever and SEC EDGAR adapters are added and we want offline-deterministic test runs. |
| **Circuit breakers** (e.g. `purgatory`, `pybreaker`) | After N consecutive failures from an external API, "trip" the breaker and short-circuit further calls for X minutes — return cached data instead of hammering a failing service. | **Slice 3** — when we have multiple data sources and outages can cascade. Slice 1 just retries with exponential backoff via `tenacity`. |
| **OpenTelemetry** | Distributed tracing. Records each request as a tree of spans (HTTP in → DB query → external API call → response) with timings. Sent to a backend like Jaeger, Honeycomb, or Datadog for visualization. | **Slice 4** — when we deploy to AWS and need to debug performance and failures in production. |
| **Trivy** | Container image scanner. Looks at your built Docker/Podman image and reports known CVEs in OS packages and Python dependencies. Runs in CI, fails the build on critical findings. | **Slice 4** — when we have a Containerfile to scan. |
| **mypy --strict** | Same as mypy but every function must have full type annotations and every check is enabled. | **Slice 4** — once the codebase is stable enough that adding annotations doesn't slow iteration. |
| **APScheduler** | In-process job scheduler. Runs `refresh_all()` every 6 hours without an external cron. | **Slice 2** — once the data layer is exercised against more than two companies. |
| **AWS Secrets Manager + IAM** | Stores API keys (USAJobs, etc.) outside the codebase; IAM grants the running container narrow read-only access. | **Slice 4** — when we deploy and have real secrets to protect. |
| **Terraform** | Infrastructure-as-code module that provisions the AWS resources (ECS Fargate or App Runner, RDS Postgres, IAM role). | **Slice 4** — when there's an AWS account to deploy into. |

### Already-active honesty constraints (from the spec)

- Revenue figures are **never fabricated**. Companies without a verified SEC filing show no revenue until Slice 3 enriches them.
- Salaries default to `salary_source = unknown` and the UI displays "Salary not disclosed" rather than guessing.
- Job freshness is shown on every result and at the top of the results list.

---

## Slice roadmap

- **Slice 1 (this commit):** Repo scaffold, FastAPI + SQLModel + SQLite, Greenhouse adapter, two seed companies (Anduril, Chainguard), filter UI, classifier heuristics, day-1 tooling.
- **Slice 2:** Lever adapter, 15–20 seed companies, APScheduler periodic refresh, vcrpy fixtures, "my fit" indicator.
- **Slice 3:** SEC EDGAR revenue enrichment, GS pay-scale lookups, salary-in-posting parsing, circuit breakers.
- **Slice 4:** Containerfile, Terraform AWS module (App Runner or ECS Fargate), GitHub Actions CI, Trivy scan, OpenTelemetry, AWS Secrets Manager, mypy --strict.

## Out of scope (for v1, per spec)

- Scraping JS-rendered career pages
- Resume parsing / matching
- Application tracking
- Authenticated access to ClearanceJobs or LinkedIn
