# Changelog

One entry per release, newest first, headed `## <tag> — YYYY-MM-DD`.
Tags are `<module>-v<major>.<minor>` and are never moved or reused.

## foundations-v1.0 — 2026-11-14

- Repository layout with one folder per module, module and spec templates
- Pipeline: formatting, lint, every module's tests, site build, secret and library scans, pipeline self-test
- Environments dev, staging and live; staging deploys on merge, live on an approved tag
- Shared logger (Python and web), environment and secrets helpers, Sentry error tracking
- Blank site with `/health`
- Setup guide: Vercel projects have no Root Directory and need `NEXT_PUBLIC_SENTRY_DSN`
