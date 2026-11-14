# Module 0 — Foundations: contract v1

Status: v1.0, fixed at stage 2 on 9 Nov 2026. This contract only grows: items can be
added, never removed or renamed. A breaking change becomes contract v2, running beside v1.

Later modules rely on exactly what is listed here and nothing else in Module 0.

## 1. Repository layout

```
modules/
  NN-<slug>/            NN = two-digit build order, slug = lowercase-hyphenated name
    spec.md             one-page spec (copied from modules/_template/spec.md)
    contract/           what the module offers later modules
    src/<package>/      code (Python package; web code lives in web/)
    tests/              the module's tests; run on every change
web/                    the website (Next.js); one app shared by all front-end modules
docs/                   setup and how-to guides
scripts/                repository tools (new_module.py, check_release_tag.py)
selftest/               the planted failing test used by the pipeline self-test
```

- A new module is created with `python scripts/new_module.py NN slug`, which copies `modules/_template/`.
- Every `modules/*/src` folder is on the Python import path for tests automatically (root `conftest.py`),
  so adding a module never edits shared configuration.
- A module imports another module only through that module's contract (its public package names listed
  in its `contract/`), never its internals.

## 2. Pipeline

File: `.github/workflows/ci.yml`. Runs on every pull request and every push to `main`.

| Job | Checks | Blocks merge |
| --- | --- | --- |
| `python` | `ruff format --check`, `ruff check`, `pytest` over every `modules/*/tests` | Yes |
| `web` | `prettier --check`, `tsc --noEmit`, `vitest run`, `next build` | Yes |
| `security` | gitleaks secret scan (full history), `pip-audit`, `npm audit --audit-level=high` | Yes |
| `selftest` | Proves a planted failing test makes the test step fail | Yes |
| `deploy-staging` | Push to `main` only, after all the above pass | — |

The required status check for the `main` branch is the job `ci-passed`, which succeeds only when
`python`, `web`, `security` and `selftest` all succeed. Later modules add tests inside their own
`tests/` folder and are picked up with no pipeline change.

## 3. Environments

| Name | Where | Web address | Database |
| --- | --- | --- | --- |
| `dev` | Developer's computer | `http://localhost:3000` | Local, or the staging project read-only |
| `staging` | Vercel project `statsmu-staging` | `https://statsmu-staging.vercel.app` (until a name is chosen) | Supabase project `statsmu-staging` |
| `live` | Vercel project `statsmu-live` | `https://statsmu-live.vercel.app` (until a name is chosen) | Supabase project `statsmu-live` |

- The current environment is read from `APP_ENV` (`dev` | `staging` | `live`); anything else is an error.
- Python: `foundations.env.current_env()`. Web: `currentEnv()` from `web/lib/env.ts`.
- Each environment exposes `GET /health` returning JSON:
  `{"status":"ok","env":"<env>","version":"<release tag or 'unreleased'>","commit":"<short sha>"}`.
  The post-deploy smoke test calls it.

## 4. Secrets

- Never stored in code or committed files. `.env.local` is git-ignored; `.env.example` lists names only.
- Stored in GitHub environment secrets (`staging`, `live`) and in each Vercel project.
- Names: `<CATEGORY>_<NAME>`, upper case, digits and underscores, at least two parts.
  Category is one of: `SOURCE` (data publishers), `DB`, `AUTH`, `SENTRY`, `EMAIL`, `VERCEL`, `API`, `APP`.
  Examples: `SOURCE_BOM_TOKEN`, `DB_URL`, `SENTRY_DSN`, `VERCEL_PROJECT_ID`.
- The same name is used in every environment; the environment decides the value.
- Python: `foundations.secrets.get_secret(name, required=True)` validates the name and reads it.

## 5. Logging

One format for Python and web: one JSON object per line on standard output.

| Field | Type | Always present | Meaning |
| --- | --- | --- | --- |
| `ts` | string | Yes | UTC time, ISO 8601 with milliseconds and `Z` |
| `level` | string | Yes | `debug` \| `info` \| `warning` \| `error` \| `critical` |
| `module` | string | Yes | Module slug, such as `foundations`, `ingestion` |
| `env` | string | Yes | `dev` \| `staging` \| `live` |
| `msg` | string | Yes | Human-readable message |
| `error` | string | On exceptions | Exception type and message |
| other keys | any JSON | No | Context passed by the caller, such as `dataset` |

- Python: `foundations.logging.get_logger("<module slug>")`, then `log.info("msg", extra={"dataset": "DF_POP"})`.
- Web: `getLogger("<module slug>")` from `web/lib/logger.ts`.
- Error-level logs and unhandled exceptions are sent to Sentry, tagged with `module` and `env`,
  when `SENTRY_DSN` is set. `foundations.errors.init_error_tracking("<module slug>")` turns this on in Python.

## 6. Releases

- Tag format: `<module slug>-v<major>.<minor>`, such as `foundations-v1.0`, `ingestion-v1.0`.
  Checked by `scripts/check_release_tag.py`.
- Every release has an entry in `CHANGELOG.md` headed `## <tag> — YYYY-MM-DD`; the release fails without it.
- Pushing a tag runs `.github/workflows/release.yml`: check tag and changelog → wait for approval
  (GitHub environment `live`) → deploy to live → smoke test `/health` → create the GitHub release.
- Tags are never moved, deleted or reused.

## 7. Templates

- `modules/_template/spec.md` — the one-page spec.
- `modules/_template/contract/README.md` — the contract outline.
- `modules/_template/tests/test_module.py` — a starter test.
