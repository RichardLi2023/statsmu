# Mauritius in numbers (working name)

Statistics Mauritius data, made easy to find, read and interpret.
Source of all data in the prototype: Statistics Mauritius.

The product is built as numbered modules. Each module is specified, given a fixed contract,
built, tested, released and then left alone. Later modules only use earlier modules'
contracts. The full plan is the "Population Prototype — Build Plan" doc.

| # | Module | Status |
| --- | --- | --- |
| 0 | Foundations | Built; awaiting account setup and staging sign-off |
| 1 | Source registry and ingestion | Not started |

## Layout

```
modules/NN-slug/   spec.md · contract/ · src/ · tests/   (one folder per module)
modules/_template/ copied by scripts/new_module.py
web/               the website (Next.js)
scripts/           new_module.py · check_release_tag.py · smoke_test.py · pipeline_selftest.py
selftest/          the planted failing test
docs/setup.md      one-off account and repository setup
```

## Working locally

```bash
# Python (3.12+)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
ruff format . && ruff check . && python -m pytest

# Website (Node 22)
cd web && cp .env.example .env.local && npm install
npm run dev        # http://localhost:3000 and http://localhost:3000/health
```

## Starting a module

```bash
python scripts/new_module.py 01 ingestion
```

Then write `spec.md` (stage 1, needs approval) and `contract/` (stage 2) before any code.

## Releasing

1. Add `## <module>-vX.Y — YYYY-MM-DD` to `CHANGELOG.md` in a pull request and merge it.
2. Tag the merged commit: `git tag ingestion-v1.0 && git push origin ingestion-v1.0`.
3. Approve the `live` deployment in GitHub → Actions. The site deploys, `/health` is checked,
   and a GitHub release is created.
