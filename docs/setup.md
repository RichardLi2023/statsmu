# One-off setup for Module 0

These steps create the accounts and settings the pipeline needs. They are done once, by
Richard, with personal accounts (not Swan accounts). Allow about 90 minutes.
Nothing here costs money on the plans named.

Names used below (change them consistently if you prefer others):

| Thing | Name |
| --- | --- |
| GitHub repository | `statsmu` (private) |
| Vercel projects | `statsmu-staging`, `statsmu-live` |
| Supabase projects | `statsmu-staging`, `statsmu-live` |
| Sentry project | `statsmu-web` |

## 1. GitHub

1. Create a personal account at github.com if you don't have one, and turn on two-factor sign-in.
2. Create a **private** repository named `statsmu`, with no README (the code already has one).
3. Upload the code. Unzip `statsmu.zip` to a folder **outside OneDrive** (for example
   `C:\Users\<you>\code\statsmu`): OneDrive syncing clashes with Git and with the website's
   thousands of library files. Install GitHub Desktop, choose *File → Add local repository*, pick
   that folder and accept *create a repository here*, make the first commit, then
   *Publish repository* (keep "private" ticked). Do this before step 1's repository creation if you
   prefer: Publish creates the repository for you.
4. In `.github/CODEOWNERS`, replace `RICHARD_GITHUB_USERNAME` with your username.

### Branch rule and approvals: a plan decision

On GitHub's free plan, a **private** repository cannot enforce branch rules or approval
gates on deployments. Two ways to get them:

| Option | Cost | Effect |
| --- | --- | --- |
| A. GitHub Pro | About USD 4 a month (check github.com/pricing) | Private code, branch rules and the live approval gate all work |
| B. Make the repository public | Free | Same protections; the code (never the secrets) is visible to anyone |

Without either, everything else still works, but "a failing test blocks a merge" and
"live needs approval" are then habits rather than enforced rules. Recommended: A.

Once on A or B, add the branch rule: *Settings → Rules → Rulesets → New branch ruleset*:

- Target: default branch (`main`)
- Restrict deletions; Block force pushes
- Require a pull request before merging. Required approvals: **0** while you are the only
  person (GitHub does not let you approve your own pull request); raise to 1 when a second
  person joins
- Require status checks to pass: add **`ci-passed`** (it appears after the pipeline has run once)

And protect tags: *New tag ruleset*, target `*-v*.*`, tick Restrict updates and Restrict deletions.

### Environments

*Settings → Environments*, create two:

- **`staging`**: no protection rules. Deployment branches: `main` only.
- **`live`**: Required reviewers: you. Deployment branches and tags: add the tag rule `*-v*.*`.

Turn on *Settings → Code security*: Dependabot alerts and security updates, and secret scanning
with push protection if offered on your plan.

## 2. Vercel (website hosting, Hobby plan)

1. Sign up at vercel.com with your GitHub account.
2. Create **two** projects, `statsmu-staging` and `statsmu-live`: Framework *Next.js*, Node 22,
   **no Root Directory** (the pipeline already runs the Vercel CLI inside `web/`; setting *web*
   here makes Vercel look for `web/web`) and **no Git connection**: deployments come only from
   GitHub Actions, so nothing reaches live without passing the pipeline.
3. In each project, *Settings → Environment Variables* (Production): `APP_ENV` = `staging` or `live`,
   and `SENTRY_DSN` plus `NEXT_PUBLIC_SENTRY_DSN` (same value, from step 4; the second reports
   browser errors).
4. Note for each project its **Project ID** (*Settings → General*), and your **Team/Org ID**
   (*Account Settings → General*, "Vercel ID").
5. Create a token: *Account Settings → Tokens*, name `github-actions`, scope your account.
6. The addresses will be `https://statsmu-staging.vercel.app` and `https://statsmu-live.vercel.app`
   (if a name is taken, Vercel adds a suffix; use whatever it shows).

## 3. Supabase (database, free plan)

1. Sign up at supabase.com with GitHub.
2. Create two projects, `statsmu-staging` and `statsmu-live`, region closest to Mauritius
   (currently South Africa or Mumbai), each with a strong generated database password saved in your
   password manager. They stay empty until Module 2.
3. Free projects pause after about a week without use; restore with one click. Upgrade before launch.

## 4. Sentry (error tracking, free Developer plan)

1. Sign up at sentry.io, create a project of type *Next.js* named `statsmu-web`.
2. Copy the **DSN** (*Project Settings → Client Keys*). It is used for both environments; Sentry
   separates them by the `environment` tag.
3. Optional, for readable stack traces: *Settings → Auth Tokens*, create an organisation token.

## 5. Secrets in GitHub

In *Settings → Environments*, add to **each** of `staging` and `live`:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `VERCEL_TOKEN` | The token from step 2.5 |
| Secret | `VERCEL_ORG_ID` | Your Vercel ID |
| Secret | `VERCEL_PROJECT_ID` | That environment's project ID |
| Secret | `SENTRY_AUTH_TOKEN` | Optional, from step 4.3 |
| Variable | `SITE_URL` | That environment's address from step 2.6 |
| Variable | `SENTRY_ORG` | Your Sentry organisation slug (optional) |
| Variable | `SENTRY_PROJECT` | `statsmu-web` (optional) |

Names follow the contract: `<CATEGORY>_<NAME>`. Secrets never go in the code.

## 6. Check the "done when" list

1. **Staging deploys on merge.** Make any small change on a branch (for example the README
   status table), open a pull request, wait for `ci-passed`, merge. *Actions* shows
   `deploy-staging` running; `SITE_URL/health` then returns `"env":"staging"`.
2. **A failing test blocks a merge.** On a branch, copy `selftest/test_planted_failure.py` into
   `modules/00-foundations/tests/`, open a pull request: `ci-passed` fails and Merge is blocked.
   Close the pull request without merging.
3. **Errors reach Sentry.** Open `https://statsmu-staging.vercel.app/api/debug-error`. Within a
   minute the error shows in Sentry with `environment: staging` and `module: foundations`.
   (This address returns 404 on live.)
4. **No secrets in the code.** The `security` job is green.
5. **Live after approval.** In `CHANGELOG.md`, change `foundations-v1.0 — UNRELEASED` to today's
   date (`YYYY-MM-DD`) through a pull request and merge it. Then in GitHub Desktop
   (*History → right-click the merge commit → Create tag*) create `foundations-v1.0` and push it.
   *Actions → release* waits for your approval; approve; `statsmu-live.vercel.app/health` then
   shows `"version":"foundations-v1.0"`.

When all five pass, sign off staging (stage 5) and Module 0 is locked.
