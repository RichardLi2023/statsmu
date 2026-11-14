# Module 0 — Foundations: spec

Status: v1.0, approved by Richard on 9 Nov 2026. The working copy with discussion is the
"Module 0 spec" tab of the Population Prototype build plan.

## Purpose

Set up the shared base that every later module is built, tested and released on, so later
modules only ever add code.

## In scope

- A GitHub repository with one folder per module, each holding `spec.md`, `contract/`, `src/` and `tests/`
- An automated pipeline that, on every change, checks formatting, runs every module's tests and builds the site
- Three environments: development, staging and live
- Automatic deployment to staging when a change is merged, and to live only from an approved tagged release
- An empty database project for staging and one for live
- A secrets store, a shared logger and error tracking (Sentry)
- Branch rules: no direct changes to `main`, and every change goes through a pull request and the pipeline
- Scanning of third-party libraries for known vulnerabilities, and of the code for leaked secrets
- The module template and the spec template, ready for Module 1

## Out of scope

Data, pages, sign-in and any user-facing feature.

## Inputs

None. This is the first module.

## Outputs

See `contract/contract.md`.

## Rules

- `main` is protected; every change goes through a pull request and the pipeline.
- Release tags are never moved or reused.
- Live deployments need Richard's approval.

## Done when

- [ ] A blank page deploys to staging automatically when a change is merged
- [ ] A tagged release deploys to live after approval
- [ ] A deliberately failing test blocks a merge
- [ ] An error raised on staging shows in Sentry within a minute
- [ ] The secret scan finds no secrets in the repository

## Tests

- Pipeline self-test: a planted failing test must make the test step fail (`selftest` job)
- Smoke test after each deployment: `GET /health` on staging and live
- Unit tests for the logger, environment, secrets and release-tag check

## Decisions (9 Nov 2026)

- Accounts owned by Richard personally; separate from Swan
- Recommended stack; no Swan IT standard applies
- Vercel default addresses until a name is chosen
- Vercel Hobby plan for the prototype; move to Pro before charging subscriptions

## Open

- Free tiers of Supabase and the API host may pause after inactivity: fine for the prototype, upgrade before launch
