# Module 1 — Source registry and ingestion: contract v1

Status: v1.0, fixed at stage 2 on 14 Nov 2026. This contract only grows: items can be added,
never removed or renamed. A breaking change becomes contract v2, running beside v1.

Later modules rely on exactly what is listed here and nothing else in Module 1.

## 0. What it uses from Module 0 (contract v1)

| Module 0 item | Use |
| --- | --- |
| Repository layout | Code in `modules/01-ingestion/`; package `ingestion` |
| Pipeline | Tests in `modules/01-ingestion/tests/` run on every change; `ci.yml` is not edited |
| Environments | `APP_ENV`; the scheduled job runs in the GitHub environment `staging` |
| Secrets | `DB_URL` (category `DB`), `SENTRY_DSN` (category `SENTRY`), read with `foundations.secrets.get_secret` |
| Logging | `foundations.logging.get_logger("ingestion")` |
| Error tracking | `foundations.errors.init_error_tracking("ingestion")` |
| Releases | Tag `ingestion-vX.Y` with a `CHANGELOG.md` entry; `release.yml` is not edited |

Files outside `modules/01-ingestion/` that this module adds or appends to (no Module 0 file is
otherwise changed):

- New: `registry/` (the source registry) and `.github/workflows/ingest.yml` (the daily pull).
- Appended: runtime libraries in `requirements.txt`, test libraries in `requirements-dev.txt`,
  the release entry in `CHANGELOG.md`, the Module 1 row in `README.md`.

## 1. Source registry

One YAML file per dataset: `registry/sources/<id>.yaml`. The file name (without `.yaml`) equals
`id`. Every file is checked against `registry/schema.json` by this module's tests on every
change, so an invalid entry blocks the merge.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | string, `^[a-z][a-z0-9_]{2,62}$` | Yes | Stable dataset id, such as `sm_df_pop`. Never reused |
| `title` | string | Yes | Publisher's title |
| `publisher` | string | Yes | Such as `Statistics Mauritius` |
| `connector` | enum: `sdmx` | Yes | Connector type. New types are added by later modules |
| `address` | object | Yes | Connector-specific; for `sdmx` see below |
| `frequency` | enum: `daily`, `weekly`, `monthly`, `quarterly`, `annual`, `irregular` | Yes | How often the publisher updates the data |
| `check_every` | enum: `day`, `week`, `month` | Yes | How often we pull it |
| `expected_release` | object: `months` (list of 1–12), `note` (string) | No | When new data is expected |
| `licence` | enum: `free_with_credit`, `all_rights_reserved`, `cc_by`, `cc_by_sa`, `odc_by`, `terms_to_confirm` | Yes | Terms of reuse |
| `licence_note` | string | No | Link or wording of the terms |
| `credit_line` | string | Yes | Shown with every figure, such as `Source: Statistics Mauritius` |
| `access_rule` | enum: `by_tier`, `free_to_all` | Yes | Must be `free_to_all` when `licence` is `all_rights_reserved` or `terms_to_confirm` |
| `themes` | list of strings, `^[a-z_]+(\.[a-z_]+)*$`, at least one | Yes | Such as `people.population` |
| `checks` | list of checks (section 5) | Yes | Run on every changed pull |
| `active` | boolean | Yes | Inactive entries are kept but never pulled |

`address` for `connector: sdmx`:

| Field | Type | Required | Example |
| --- | --- | --- | --- |
| `base_url` | https URL ending in `/` | Yes | `https://databrowser.govmu.org/ws/NSI_WS/rest/` |
| `agency` | string | Yes | `MU1` |
| `dataflow` | string | Yes | `DF_POP` |
| `version` | string | Yes | `1.0` |
| `key` | string | No (default `all`) | `all` |

On every run, all registry files are mirrored into `ingestion.sources` (section 3).

## 2. Connector contract

Every connector implements three methods. Connectors never touch the database; the runner does.

```python
class Connector(Protocol):
    type: str  # matches registry `connector`

    def discover(self, entry: SourceEntry) -> Discovery: ...
    def fetch(self, entry: SourceEntry) -> list[RawArtefact]: ...
    def parse(self, entry: SourceEntry, artefacts: list[RawArtefact]) -> Parsed: ...
```

| Type | Fields |
| --- | --- |
| `Discovery` | `latest_period: str \| None`, `observation_count: int \| None`, `last_updated: datetime \| None`, `details: dict` |
| `RawArtefact` | `kind: str` (`data` or `structure`), `url: str`, `http_status: int`, `media_type: str`, `content: bytes` |
| `Parsed` | `rows: list[StandardRow]`, `labels: dict[str, dict[str, str]]` (concept → code → label), `structure_fingerprint: str \| None` |
| `StandardRow` | `dataset: str` (registry `id`), `dimensions: dict[str, str]` (every dimension except time, as codes), `period: str`, `value: Decimal \| None`, `attributes: dict[str, str]` (empty values left out) |

The `sdmx` connector:

- `discover`: `availableconstraint/{agency},{dataflow},{version}/all/all/all` (observation count,
  period range) and `dataflow/{agency}/{dataflow}/{version}` (`LAST_UPDATE` annotation), as SDMX-JSON.
- `fetch`: `data/{agency},{dataflow},{version}/{key}/ALL/?dimensionAtObservation=AllDimensions`
  as SDMX-CSV 1.0 (`kind = data`), and
  `dataflow/{agency}/{dataflow}/{version}/?detail=Full&references=Descendants` as SDMX-JSON
  (`kind = structure`).
- `parse`: `dimensions` = every column between `DATAFLOW` and `TIME_PERIOD` (for DF_POP: `FREQ`,
  `REF_AREA`, `INDIC_POP`, `SEX`, `AGE`); `period` = `TIME_PERIOD`; `value` = `OBS_VALUE`;
  `attributes` = the remaining columns. `labels` come from the structure's code lists, keyed by
  dimension or attribute id. `structure_fingerprint` ignores the message header, which changes
  on every request.
- Each request: 60-second timeout, up to 3 attempts, `User-Agent: statsmu-ingestion/<version>`.

## 3. Database (Supabase, schema `ingestion`)

Created and extended only by numbered, add-only migration files in
`modules/01-ingestion/src/ingestion/migrations/`, applied by `python -m ingestion migrate` and
recorded in `ingestion.schema_migrations`. The schema is not exposed to the Supabase web API, and
row-level security is on for every table.

`ingestion.sources`: the registry as last mirrored.

| Column | Type | Notes |
| --- | --- | --- |
| `source_id` | text, primary key | Registry `id` |
| `connector` | text | |
| `active` | boolean | |
| `licence` | text | |
| `access_rule` | text | |
| `credit_line` | text | |
| `themes` | text[] | |
| `definition` | jsonb | The full registry entry |
| `updated_at` | timestamptz | |

`ingestion.raw_pulls`: one row per pull of one source.

| Column | Type | Notes |
| --- | --- | --- |
| `pull_id` | bigint, identity, primary key | Always increasing |
| `source_id` | text → `sources` | |
| `started_at`, `finished_at` | timestamptz | `finished_at` null while running |
| `status` | text: `running`, `ok`, `failed` | |
| `error` | text | Set when `failed` |
| `trigger` | text: `schedule`, `manual` | |
| `code_version` | text | Release tag or short commit |
| `discovery` | jsonb | The `Discovery` result |
| `content_checksum` | text | SHA-256 of the sorted, normalised rows (section 4) |
| `structure_checksum` | text | SHA-256 of `structure_fingerprint` |
| `row_count` | integer | |
| `changed` | boolean | True when this pull raised a `new_data` event |

`ingestion.raw_pull_files`: the raw files received in each pull, byte for byte.

| Column | Type | Notes |
| --- | --- | --- |
| `pull_id` | bigint → `raw_pulls` | Primary key with `kind` |
| `kind` | text | `data` or `structure` |
| `url` | text | |
| `http_status` | integer | |
| `media_type` | text | |
| `size_bytes` | integer | |
| `sha256` | text → `raw_blobs` | Checksum of the raw bytes |

`ingestion.raw_blobs`: the file contents, stored once per checksum. Read only through `read_raw()`;
its layout may change in a later version without breaking this contract.

`ingestion.staging_batches`: one per changed pull.

| Column | Type | Notes |
| --- | --- | --- |
| `batch_id` | bigint, identity, primary key | |
| `pull_id` | bigint → `raw_pulls`, unique | |
| `source_id` | text | |
| `row_count` | integer | |
| `checks` | jsonb | List of `{"check": str, "passed": bool, "detail": str}` |
| `status` | text: `checks_passed`, `checks_failed` | |
| `created_at` | timestamptz | |

`ingestion.staged_rows`: the full standard rows of each batch (a complete copy of the dataset, not
only the changes).

| Column | Type | Notes |
| --- | --- | --- |
| `batch_id` | bigint → `staging_batches` | Primary key with `row_no` |
| `row_no` | integer | |
| `dimensions` | jsonb | Object of code pairs |
| `period` | text | |
| `value` | numeric | Null when the publisher gives no value |
| `attributes` | jsonb | Object of code pairs |

`ingestion.code_labels`: the latest labels for every code, replaced when the structure changes.

| Column | Type | Notes |
| --- | --- | --- |
| `source_id` | text | Primary key with `concept`, `code` |
| `concept` | text | Dimension or attribute id, such as `AGE` |
| `code` | text | Such as `Y_GE85` |
| `label` | text | Such as `85 years old and over` |
| `pull_id` | bigint | Pull the labels came from |

`ingestion.events`: the "new data" events.

| Column | Type | Notes |
| --- | --- | --- |
| `event_id` | bigint, identity, primary key | Always increasing; consumers keep the last one they read |
| `event_type` | text | `new_data` (more types may be added) |
| `source_id` | text | |
| `pull_id` | bigint | The pull that changed |
| `previous_pull_id` | bigint | Null on the first pull of a source |
| `batch_id` | bigint | The staging batch holding the new rows |
| `initial` | boolean | First pull of this source |
| `added`, `removed`, `revised` | integer | Row counts against the previous batch |
| `periods_affected` | text[] | Sorted |
| `structure_changed` | boolean | |
| `checks_passed` | boolean | |
| `created_at` | timestamptz | |

A pull, its files, its batch, its rows and its event are written in one transaction.

## 4. Change detection

- Rows are normalised (codes trimmed, value written as a plain decimal with no trailing zeros,
  empty attributes removed), turned into one canonical JSON line each, sorted, and hashed with
  SHA-256 to give `content_checksum`.
- A pull raises exactly one `new_data` event when its `content_checksum` or `structure_checksum`
  differs from the last `ok` pull of the same source, or when there is no earlier `ok` pull.
  Otherwise it raises none, and no batch is written.
- A row's key is its dimensions plus period. Against the previous batch: `added` = keys only in
  the new pull, `removed` = keys only in the old, `revised` = same key with a different value or
  attributes.
- `checks_passed = false` does not stop the event; consumers decide what to do with it.

## 5. Validation checks

Each registry check is an object with `type` and its fields. Results go to
`staging_batches.checks`.

| `type` | Fields | Passes when |
| --- | --- | --- |
| `min_rows` | `value` | At least `value` rows |
| `required_dimensions` | `dimensions` (list) | Every row has these dimensions |
| `unique_key` | — | No two rows share dimensions and period |
| `numeric_values` | — | Every value is a number or empty |
| `periods_complete` | `from` | Every period from `from` to the latest is present (annual, quarterly, monthly) |
| `sum_equals` | `dimension`, `total`, `tolerance` (default 0) | For each group of rows equal in all other dimensions and period, the `total` row equals the sum of the other codes of `dimension`, when both exist |

## 6. Running

| Command | Does |
| --- | --- |
| `python -m ingestion migrate` | Applies pending migrations |
| `python -m ingestion check-registry` | Validates every registry file; no network or database |
| `python -m ingestion run [--source ID] [--trigger schedule\|manual]` | Mirrors the registry, then pulls every active source that is due (or only `ID`) |
| `python -m ingestion smoke [--source ID]` | Discovers and fetches from the live publisher; no database |

`run` exits non-zero if any pull failed, after finishing the others. A source is due when
`check_every` has passed since its last `ok` pull (day: 20 hours; week: 6 days; month: 27 days).

Workflow `.github/workflows/ingest.yml`: every day at 01:43 UTC (05:43 Mauritius) and on demand
(*Actions → ingest → Run workflow*). Runs in the GitHub environment `staging` with `APP_ENV=staging`,
`DB_URL` and `SENTRY_DSN`. Scheduled runs use the code of the latest `ingestion-v*` release (`main` until the first release);
manual runs use the chosen branch. Each run re-enables the workflow so GitHub's 60-day pause never applies.

## 7. Public Python names

The only names other modules may import:

| Name | Purpose |
| --- | --- |
| `ingestion.connect()` | A database connection (psycopg 3) using `DB_URL` |
| `ingestion.registry.load(path=None) -> list[SourceEntry]` | Read and validate the registry |
| `ingestion.registry.SourceEntry` | One registry entry |
| `ingestion.connectors.Connector`, `Discovery`, `RawArtefact`, `Parsed`, `StandardRow` | Section 2 |
| `ingestion.connectors.get_connector(type) -> Connector` | Connector for a registry `connector` value |
| `ingestion.read_raw(conn, pull_id, kind="data") -> bytes` | The raw bytes of one pull |
| `ingestion.staged_rows(conn, batch_id) -> Iterator[StandardRow]` | The rows of a staging batch |
| `ingestion.events_since(conn, after_event_id=0) -> list[Event]` | Events with a larger `event_id`, oldest first |
| `ingestion.Event` | One row of `ingestion.events` |

## 8. Contract tests

| Item | Test file |
| --- | --- |
| Registry schema and the "all rights reserved is free" rule | `tests/test_registry.py` |
| Connector contract and SDMX parsing (recorded DF_POP files) | `tests/test_sdmx.py` |
| Normalisation, checksums and the diff | `tests/test_change_detection.py` |
| Validation checks | `tests/test_checks.py` |
| Tables, one-transaction writes and events (local PostgreSQL) | `tests/test_store.py` |
| Public Python names | `tests/test_contract.py` |
