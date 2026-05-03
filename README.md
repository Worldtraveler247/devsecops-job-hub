# DevSecOps Job Hub

A focused web app that surfaces **entry-level cleared / clearable cloud-security and DevSecOps roles** at U.S. government contractors and defense-tech companies — with deliberate filtering so generic senior listings don't drown the postings someone actually breaking into the field can apply to.

All four planned slices (build, expand, enrich, deploy-ready) are shipped. The hub aggregates four real sources, enriches public companies with SEC 10-K revenue, calibrates private-sector salaries against the GS pay scale, and runs through GitHub Actions CI on every push.

---

## What it does

| Capability | How it works |
|---|---|
| **Pulls live job postings** from Greenhouse public boards, Lever public postings, USAJobs Search API, and The Muse public jobs API | Async `httpx` adapters with `tenacity` retry and per-host circuit breakers |
| **Drops out-of-scope postings at ingest** | Senior+ titles, unclassified non-tech roles, and non-IT noise are hard-deleted before they ever reach the UI |
| **Enriches public companies with SEC 10-K revenue** | EDGAR XBRL companyconcept endpoint; never fabricates a number |
| **Parses salary ranges from postings** | Lever's structured `salaryRange` field + a regex parser for Greenhouse description text, with plausibility bounds and an honesty default of "not disclosed" |
| **Maps salary → GS-grade equivalent** | 2025 GS table, DC locality — gives transitioning service members and federal hires an immediate calibration |
| **Flags "★ Good Fit" jobs against a profile** | Env-driven `FitProfile` with role-family / clearance-ceiling / OCONUS / remote rules; per-row reasons in the UI |
| **Auto-refreshes via APScheduler** | Optional in-process scheduler runs `refresh_all()` on an interval; tests don't trigger it |
| **OpenTelemetry-instrumented** | Optional FastAPI / SQLAlchemy / httpx auto-instrumentation; console exporter by default |

Live distribution after a fresh refresh on the seeded sources: ~450 active jobs, ~12 fits against the default profile (RHCSA + Sec+ + military bg, clearable to Secret).

---

## Tech stack

- **Python 3.12**, **FastAPI** (server-rendered, no SPA)
- **SQLModel** on **SQLite** for dev (Postgres-ready via `DATABASE_URL`)
- **httpx** (async) + **tenacity** for retry; custom **circuit breakers** per host
- **APScheduler** for periodic refresh (off by default in tests/CI)
- **OpenTelemetry** SDK + auto-instrumentors for FastAPI / SQLAlchemy / httpx
- **Jinja2** templates + plain CSS, styled to match the App Hub aesthetic
- **pytest** + **vcrpy** (`pytest-recording`) for offline-deterministic adapter tests
- **ruff**, **mypy --strict**, **bandit**, **gitleaks** in pre-commit + CI
- Multi-stage **Containerfile** (Podman/Docker compatible), scanned by **Trivy** in CI

---

## Quick start

```bash
# 1. Create venv and install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure (optional but recommended)
cp .env.example .env
# Edit .env to add:
#   EDGAR_CONTACT_EMAIL=you@example.com   # required by SEC fair-use
#   USAJOBS_API_KEY=...                   # free at developer.usajobs.gov
#   USAJOBS_CONTACT_EMAIL=you@example.com
# Without these, the affected adapters skip silently — the app still runs.

# 3. Run the test suite (offline; vcrpy cassettes ship with the repo)
pytest

# 4. Start the dev server
.venv/bin/uvicorn devsecops_job_hub.main:app --host 127.0.0.1 --port 8000 --app-dir src

# 5. In a separate terminal, pull live job postings
curl -X POST http://127.0.0.1:8000/admin/refresh

# 6. Open http://127.0.0.1:8000/
```

### Restarting

If port 8000 is already bound (you'll see "address already in use"):

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
```

Then re-run the uvicorn line.

### Optional: enable OpenTelemetry traces

```bash
OTEL_ENABLED=true .venv/bin/uvicorn devsecops_job_hub.main:app \
  --host 127.0.0.1 --port 8000 --app-dir src
```

Span trees print to stdout via the console exporter. Swap `ConsoleSpanExporter` in `services/telemetry.py` for an OTLP exporter to send to Honeycomb / Tempo / Jaeger / Datadog — instrumentation calls don't change.

### Optional: enable the periodic refresh scheduler

```bash
ENABLE_SCHEDULER=true SCHEDULER_INTERVAL_HOURS=6 .venv/bin/uvicorn ...
```

---

## Configuration (`.env`)

All settings are env-driven via `pydantic-settings`. Defaults are in `src/devsecops_job_hub/config.py`. Common ones:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./jobs.db` | SQLite for dev; swap to a Postgres DSN for prod |
| `LOG_LEVEL` | `INFO` | Standard Python log levels |
| `ENABLE_SCHEDULER` | `false` | Turn on the in-process APScheduler |
| `SCHEDULER_INTERVAL_HOURS` | `6` | Hours between automatic refreshes |
| `FIT_ROLE_FAMILIES` | `linux_admin,security_officer,soc_analyst,sys_security_eng,cloud_security_eng,devsecops_eng,security_eng_infra,cloud_engineer` | Comma-list of role families that count as a "★ Good Fit" |
| `FIT_CAREER_STAGES` | `entry` | Career stages to include — set to `entry,mid` to loosen |
| `FIT_MAX_CLEARANCE` | `secret` | Highest clearance you'd pursue (`none`, `public_trust`, `secret`, `top_secret`, `ts_sci`, `ts_sci_poly`) |
| `FIT_REMOTE_ONLY` | `false` | If true, only remote postings can be a fit |
| `FIT_ALLOW_OCONUS` | `false` | If true, overseas postings are eligible |
| `EDGAR_CONTACT_EMAIL` | (empty) | Required by SEC fair-use; without it, EDGAR enrichment is skipped |
| `USAJOBS_API_KEY` | (empty) | Free at https://developer.usajobs.gov; without it, the USAJobs adapter is skipped |
| `USAJOBS_CONTACT_EMAIL` | (empty) | Sent in `User-Agent` per USAJobs docs |
| `OTEL_ENABLED` | `false` | Toggle OpenTelemetry instrumentation |
| `OTEL_SERVICE_NAME` | `devsecops-job-hub` | The `service.name` resource attribute on every span |

---

## Project structure

```
src/devsecops_job_hub/
├── main.py                 # FastAPI app, routes, lifespan (init_db + seed + telemetry + scheduler)
├── config.py               # Pydantic settings (env-driven)
├── db.py                   # SQLModel engine + session
├── models.py               # Company, Job, all enums
├── classify.py             # Title-only role-family classifier; description-aware stage + clearance
├── adapters/
│   ├── base.py             # ATSAdapter Protocol
│   ├── greenhouse.py       # Greenhouse public boards (?content=true; HTML-stripped)
│   ├── lever.py            # Lever public postings (mode=json; structured salaryRange)
│   ├── usajobs.py          # USAJobs Search API; structured SecurityClearanceRequired
│   └── muse.py             # The Muse public jobs (multi-employer aggregator)
├── services/
│   ├── refresh.py          # Adapter dispatch, idempotent upsert, audience purge
│   ├── enrich.py           # Companies with tickers → SEC EDGAR revenue
│   ├── edgar.py            # SEC XBRL client (companyconcept endpoint, ticker→CIK cache)
│   ├── salary_parse.py     # Anchored regex parser for free-text salary ranges
│   ├── gs_scale.py         # 2025 GS table → grade equivalence for private salaries
│   ├── fit.py              # FitProfile + compute_fit (pure functions)
│   ├── breakers.py         # Custom per-host circuit breakers (no extra deps)
│   └── telemetry.py        # Optional OpenTelemetry initialization
├── seed/
│   └── companies.py        # Hand-curated initial company list (verified slugs)
├── templates/              # Jinja templates (base + jobs page)
└── static/                 # CSS

tests/
├── conftest.py                          # tmp SQLite + vcrpy slim-body filter for cassettes
├── test_app.py                          # FastAPI smoke + form-empty-values regression
├── test_classify.py                     # Pure unit tests on classifier (title + description paths)
├── test_breakers.py                     # Circuit-breaker state machine with FakeClock
├── test_fit.py                          # FitProfile / compute_fit pure-function tests
├── test_gs_scale.py                     # GS-grade boundary tests
├── test_salary_parse.py                 # Salary regex coverage (anchors, K-suffix, plausibility)
├── test_edgar.py                        # SEC EDGAR client + vcrpy live-API check
├── test_greenhouse_adapter.py           # MockTransport adapter test + breaker-trip integration
├── test_greenhouse_recorded.py          # vcrpy cassette test against live Greenhouse
├── test_lever_adapter.py                # MockTransport adapter test + salary-range cases
├── test_lever_recorded.py               # vcrpy cassette test against live Lever
├── test_muse_adapter.py                 # MockTransport adapter test + breaker-trip
├── test_usajobs_adapter.py              # MockTransport adapter test + breaker-trip + key-skip
├── cassettes/                           # vcrpy YAML cassettes (committed for offline CI)
└── fixtures/                            # JSON sample payloads
```

119 tests; the full suite is offline-deterministic.

---

## Architecture (data flow)

```
            ┌────────────────────── refresh_all() ──────────────────────┐
            │                                                           │
  Greenhouse│  Lever     USAJobs    The Muse                            │
   adapter ─┘   adapter   adapter   adapter                             │
       │           │         │         │                                │
       │ httpx +   │         │         │  Per-host circuit breakers     │
       │ tenacity  │         │         │  (greenhouse / lever / muse /  │
       │           │         │         │   usajobs / edgar)             │
       v           v         v         v                                │
   Title-only role classifier  +  description-aware stage + clearance   │
                       │                                                │
                       v                                                │
            Idempotent upsert (company_id, apply_url)                   │
                       │                                                │
                       v                                                │
   _purge_senior():  hard-delete role_family=None  +  career_stage=SENIOR
                       │                                                │
                       v                                                │
            enrich_companies():  EDGAR 10-K revenue per ticker          │
            ─────────────────────────────────────────────────────────────┘

           HTTP GET / →  SQLModel query →  compute_fit per row →  Jinja render
                                                  │
                                                  └─ fit profile from Settings (env-driven)
```

Two cross-cutting concerns sit alongside this flow: **OpenTelemetry** auto-instrumentation captures spans on every adapter HTTP call, every SQL query, and every HTTP request when `OTEL_ENABLED=true`. **APScheduler** can drive `refresh_all()` on a 6-hour interval when `ENABLE_SCHEDULER=true`.

### Honesty constraints (hard rules)

- **Revenue figures are never fabricated.** A company without a current-year 10-K entry under any known revenue concept stays at `annual_revenue_usd=None`.
- **Salaries default to `salary_source=unknown`.** UI shows "Salary not disclosed" rather than guessing — no annualized hourly conversions, no non-USD coercion.
- **GS grades are explicitly approximate** ("~GS-13") and tooltip-cited to the 2025 DC locality table. Not a federal job offer.
- **Senior+ postings are dropped at ingest, not just hidden.** Audience rule is enforced server-side; the UI never had to filter.

---

## Tooling

Every item that was originally listed as "deferred" is now in place. The table below reflects the current state.

| Tool | What it does | Status |
|---|---|---|
| **ruff** | Lint + format check | ✓ in CI |
| **pytest** | Test runner | ✓ 119 tests, offline |
| **mypy --strict** | Full strict type checking | ✓ in CI; 23 source files clean |
| **bandit** | Security-focused Python linter | ✓ via pre-commit |
| **gitleaks** | Pre-commit secret scanner | ✓ via pre-commit |
| **pre-commit** | Hook orchestrator | ✓ |
| **vcrpy** (`pytest-recording`) | Records / replays HTTP for adapter tests | ✓ Greenhouse + Lever + EDGAR cassettes committed |
| **tenacity** | Exponential-backoff retry on transport errors | ✓ on every adapter |
| **Custom circuit breakers** | Per-host, ~100-line state machine | ✓ in `services/breakers.py` (no `purgatory`/`pybreaker` dep) |
| **APScheduler** | In-process periodic refresh | ✓ opt-in via `ENABLE_SCHEDULER=true` |
| **OpenTelemetry** | Distributed tracing | ✓ opt-in via `OTEL_ENABLED=true`; console exporter by default |
| **Containerfile** (multi-stage) | Reproducible OCI build | ✓ ~200MB runtime, non-root, /healthz HEALTHCHECK |
| **Trivy** | OCI image CVE scanner | ✓ in CI; SARIF → Code Scanning + HIGH/CRITICAL gate |
| **GitHub Actions** | CI: ruff + mypy + pytest + image build + Trivy | ✓ runs on every push and PR to `main` |

### Skipped (project-scope decision, not deferred)

- **AWS deploy** (Terraform, RDS, App Runner, Secrets Manager) — out of scope for this build under a no-paid-hosting constraint. The Containerfile + CI is enough portfolio evidence for "deploy this anywhere with a container runtime."

---

## Slice roadmap (all shipped)

| Slice | Deliverables | Final commits |
|---|---|---|
| **1** | Repo scaffold; FastAPI + SQLModel + SQLite; Greenhouse adapter; 2 seed companies (Anduril, Chainguard); filter UI; classifier heuristics; day-1 tooling (ruff / pytest / mypy / bandit / gitleaks / pre-commit) | `1e4c743` |
| **2** | Lever adapter; 20 verified seed companies; APScheduler; vcrpy cassettes; "★ My Fit" indicator; description-aware classifier; senior + non-tech audience purge | `c1fe462`, `a2d47e7`, `41e6ccb`, `ddd71e7`, `aaa391c` |
| **3** | Salary parsing (Lever structured + Greenhouse regex); SEC EDGAR revenue enrichment for 5 public tickers; GS pay-grade equivalence; custom circuit breakers | `fb7f0c9`, `b2ebe93`, `188c7fb`, `4fd24ed` |
| **4** | Containerfile; GitHub Actions CI; mypy --strict; Trivy SARIF + HIGH/CRITICAL gate; OpenTelemetry instrumentation | `0efacde`, `bb7ba9b`, `9962a72`, `5da5507`, `b91c3f3` |

Plus follow-ups: USAJobs adapter (`dc84af0`), The Muse adapter + `SOFTWARE_ENGINEER` catch-all (`116669c`), classifier tightening + fit-profile tuning to actual candidate skills (`3b69992`), filter-form empty-value fix (`ac530b8`).

---

## Out of scope (deliberate)

- **Scraping JS-rendered career pages.** Out per spec; brittle and AUP-risky.
- **Resume parsing / matching.** Different problem; the hub's value is curation + audience filtering, not resume tailoring.
- **Application tracking.** A cleared candidate already has a tracker (or should). Adding one would expand the surface for marginal value.
- **Authenticated access to ClearanceJobs or LinkedIn.** ClearanceJobs has no public API and scraping a paid platform is legally murky. LinkedIn's API is closed. USAJobs (federal) and the public ATS APIs (Greenhouse / Lever / Muse) cover the legal-and-public space.
- **Paid AWS deploy.** See "Skipped" above.

---

## License

MIT (see `LICENSE` if present, otherwise treat as MIT). Recipients of any deployed instance should be told plainly that data freshness depends on when `/admin/refresh` last ran, and that GS-grade labels are approximate.
