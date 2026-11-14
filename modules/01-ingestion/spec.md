# Module 1 — Source registry and ingestion: spec

Status: v1.0, approved by Richard on 14 Nov 2026, with the DF_POP registry values and release
timing as proposed. The working copy with discussion is the "Module 1 spec" tab of the
Population Prototype build plan.

## Purpose

Bring data in from publishers automatically and keep an unchanged copy of every pull, so later
modules always work from the source as received and learn when something new has arrived.
Adding a dataset is a registry entry, not a code change.

## What the live feed shows (checked 14 Nov 2026)

- **Address.** The SDMX service is `https://databrowser.govmu.org/ws/NSI_WS/rest/`. DF_POP is
  `MU1,DF_POP,1.0`: 1,159 observations, annual, 2007–2025, last updated 7 Aug 2026.
- **Area.** Republic only: every observation has `REF_AREA = MU`. The code list also has Island of
  Mauritius and Island of Rodrigues, but DF_POP holds no data for them. Mid-year figures exclude
  Agalega and St Brandon; end-year figures include them.
- **Two indicators.** `POP_MIDY` has sex × age for every year (1,140 rows); `POP_EOY` is one total
  per year (19 rows).
- **Age bands.** 19 bands plus a total: `Y0`, `Y1T4`, `Y5T9` … `Y80T84`, `Y_GE85`, `_T`.
  Ages add up to the total and males plus females equal the total (checked for 2007 and 2025).
- **Provisional figures.** Not marked: every observation is `OBS_STATUS = E`, including 2025.
- **Revisions.** Overwritten in place; notes record census rebasing. No earlier versions are
  kept and `updatedAfter` is ignored, so our raw store is the only record of past figures and
  change detection compares whole pulls.
- **Light check.** The availability query gives the observation count and period range (~1 KB);
  the dataflow carries a `LAST_UPDATE` date. Neither is trusted alone.

## In scope

- Source registry: one YAML file per dataset in `registry/sources/`, checked against a schema
- Connector contract (discover, fetch, parse) and the SDMX connector
- Daily scheduled pull on GitHub Actions at 05:43 Mauritius time, plus manual runs
- Raw store: every pull saved byte for byte with pull time, HTTP status, size, SHA-256 and code
  version; identical files stored once
- Change detection raising a `new_data` event that lists what was added, removed and revised
- Staging area: parsed rows of each changed pull in one standard layout, with check results
- The DF_POP registry entry, and a second test entry proving a new dataset needs no code

## Out of scope

- The clean observations table (Module 2), plain-language names (Module 3), alerts (Module 10),
  the approvals screen (Module 11)
- Spreadsheet, PDF and other API connectors (later modules, same contract)
- A live database (`statsmu-live` stays deferred)

## Inputs

Module 0 contract v1. Nothing in Module 0 changes.

## Where the raw store lives

Supabase project `statsmu-staging`, schema `ingestion`, raw files stored once per checksum and
read only through `read_raw()`. Rejected: files in the public repository (republishes raw data,
cannot commit to `main` from a schedule, history grows forever) and GitHub Actions artifacts
(deleted after at most 90 days).

## Outputs (its contract)

See `contract/contract.md`: the registry, the connector contract, tables `ingestion.sources`,
`raw_pulls`, `raw_pull_files`, `raw_blobs`, `staging_batches`, `staged_rows`, `code_labels` and
`events`, and the public Python names.

## Rules

- Raw files are never edited or deleted; failed pulls are recorded with their error.
- Change is judged on content (sorted, normalised rows), not bytes.
- A new dataset of an existing connector type needs only a registry file in a pull request.
- Licence, credit line and access rule are required; "all rights reserved" forces free access.
- The database is reached only with `DB_URL`, through Supabase's session pooler.
- Tests never touch Supabase; they use a temporary local PostgreSQL.

## Done when

- [ ] The daily pull of DF_POP runs unattended for three consecutive days on the schedule.
- [ ] A changed figure raises exactly one `new_data` event naming the changed observation; an
      unchanged or reordered pull raises none.
- [ ] A second dataset is pulled, stored and staged after adding only its registry file.
- [ ] A failed pull is recorded as `failed` and reaches Sentry tagged `module=ingestion`.

## Tests

- Connector tests on recorded copies of DF_POP, with no network
- Registry schema tests, including a file missing its licence
- Change detection: identical, reordered, revised value, added row, removed row, changed attribute
- Contract tests on the tables and public Python names
- Live smoke test (manual and in the daily job)

## Risks and open questions

- Reaching the feed from GitHub's runners: checked first in stage 3.
- GitHub pauses schedules after 60 days without commits: the job re-enables itself.
- Feed shape changes: flagged on the event as a structure change.
- The Supabase database password must be reset now and stored as `DB_URL` (Richard).
- Decided 14 Nov 2026: DF_POP licence "free to use with credit", credit "Source: Statistics
  Mauritius", access "by tier", theme People: population; expected release annually around
  August. The "provisional" label for the latest year is left to Module 3.

## Changelog

| Version | Date | Change |
| --- | --- | --- |
| v1.0 | 14 Nov 2026 | Spec approved |
| v0.1 | 14 Nov 2026 | First draft |
