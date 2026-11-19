# Dependencies

The plan is [`PLAN.md`](PLAN.md).
Started 2026-11-19 by the project's review, from the repository, its workflows and `gh` listings, after the build had created everything below; dates are from the plan and from `gh secret list`.

## Accounts and services

- **Cloudflare Workers Free** — no card; 100,000 requests a day, 10 ms of CPU a request, 1,000 KV writes a day; used by the API; opened 2026-11-18 by the owner (Q5), subdomain `henrymckay.workers.dev`; holds the Worker `market-data-api` with its secret `MOTHERDUCK_TOKEN` and its cron `*/15 * * * *`, and the KV namespace `market-data-api-cache`; removed by `npx wrangler delete` in `api/` after `npx wrangler login`, or in the dashboard under Workers & Pages, then the namespace under Storage & Databases, KV.
- **GitHub** — the owner's account, free; public repository `henrymckay/market-data-public`, whose Actions are free for a public repository and whose schedules stop after 60 days without activity; used by the pipeline, the monitor, the deploys and the dashboard; created 2026-11-18; holds the workflows `nightly`, `watch`, `universe`, `site`, `api` and `verify-secrets`, the Pages site <https://henrymckay.github.io/market-data-public/> (source: GitHub Actions), the five repository secrets below and the repository variable `API_URL`; removed by `gh repo delete henrymckay/market-data-public --yes`, which takes the runs, secrets, variable and Pages site with it.
- **MotherDuck Lite** — the owner's account, no card; 10 GB and 10 CU-hours a month included, usage not readable on Lite (I22); used by the pipeline, the monitor and the API; the account predates the project; holds the database `market_data` (created 2026-11-18), the read-only share `market_data_api` of it (attached in the owner's account as `shr`) and the service account `market_data_api`; removed by the README's Tear it down commands (`drop database market_data`, `drop share market_data_api`, and a `DELETE` of the service account on MotherDuck's REST API).
- **ntfy.sh** — the public server, used anonymously with no account; 250 messages a day per address, attachments kept 3 hours; used by the alerts; holds only the topic, which exists while anyone publishes or subscribes to it; removed by deleting the secret and the keychain entry and unsubscribing the phone.
- **Wikipedia** — read once a month by `universe sync`, no account.
- **Yahoo Finance** — read every night through `yfinance`, no account, unpublished rate limit.

## Credentials

- **`CLOUDFLARE_ACCOUNT_ID`** — names the Cloudflare account (an identifier, kept as a secret); kept in the repository secrets; read by `api.yml`'s deploy and `verify-secrets.yml`; set 2026-11-18; never rotated; goes with the account.
- **`CLOUDFLARE_API_TOKEN`** — the owner's token from the "Edit Cloudflare Workers" template, scoped to their one account; kept in the repository secrets only; read by `api.yml`'s deploy and `verify-secrets.yml`'s `wrangler tail`; created 2026-11-18, rotate by 2027-02-15; revoked under My Profile, API Tokens.
- **`GITHUB_TOKEN`** — Actions' own per-run token; `universe.yml` asks for `contents: write` (to commit `universe.csv`) and `actions: write` (to re-enable the schedules); nothing to rotate or revoke.
- **`MOTHERDUCK_API_TOKEN`** — the service account `market_data_api`'s token, read-write at the account level (Lite has no read-only token) but seeing `market_data` only through the read-only share; kept in the repository secrets and copied by `api.yml` into the Worker secret `MOTHERDUCK_TOKEN`; read by the Worker and `verify-secrets.yml`; created 2026-11-18, rotate by 2027-02-15; revoked by deleting the service account.
- **`MOTHERDUCK_TOKEN`** — the owner's own MotherDuck access token, read-write on every database in the account (A1; Q1's service account is not built); kept in the macOS keychain under service `motherduck-token` and in the repository secrets; read by `nightly.yml`'s `nightly` and `notify` jobs, `watch.yml` and `verify-secrets.yml`, and locally by the README's commands; created 2026-11-18, rotate by 2027-02-15; revoked in MotherDuck under Settings, Access tokens.
- **`NTFY_TOPIC`** — the alert topic, the only key to the channel; kept in the macOS keychain under service `ntfy-market-monitor` and in the repository secrets; read by `notify`, `status --alert`, every workflow's failure step and `verify-secrets.yml`; created 2026-11-18 by `scripts/make_topic.py`; rotated only if leaked (`make_topic.py --rotate`, then the phone subscribes again); revoked by deleting both copies.

## Tools

- **`duckdb` CLI** — needed by the README's queries and teardown; installed on the owner's machine, not by the project.
- **`gitleaks` 8.30.1** — needed by the pre-commit hook; installed by `pre-commit` from its pinned `rev`.
- **Google Chrome** — needed by the browser smokes (`pytest -m slow`, through `CHROME`); installed on the owner's machine.
- **macOS `security`** — needed to read the token and the topic from the keychain; part of macOS.
- **Node 24** — needed by the dashboard and the API; installed with `uv sync` through the development dependency `nodejs-wheel`.
- **`pre-commit`** — needed by the hooks; installed with `uv sync`, then `uv run pre-commit install` once per clone.
- **Python 3.14** — needed by the build and the run; installed by `uv` from `.python-version`.
- **`uv`** — needed by the build, the run and every workflow; installed with `curl -LsSf https://astral.sh/uv/install.sh | sh`, and on Actions by `astral-sh/setup-uv` v10.3.3.
- **`wrangler` 4** — needed to run and deploy the API; installed with `uv run npm --prefix api ci`, and on Actions by `cloudflare/wrangler-action` v4.1.3.
- **GitHub Actions** — `actions/checkout` v7.0.1, `actions/deploy-pages` v5.0.1, `actions/upload-pages-artifact` v5.0.0, `astral-sh/setup-uv` v10.3.3 and `cloudflare/wrangler-action` v4.1.3, each pinned to its commit in the workflows.

## Connectors and plugins

- **MotherDuck connector (claude.ai)** — read the owner's database list before the first migration (A12), and read-only queries during the review.
- **Claude Code plugins `manage-project`, `run-project`, `structure-app` and `write-code`** — the skills the plan, build and review followed.

## Packages

The lock files list them: `uv.lock`, `api/package-lock.json` and `web/package-lock.json`.
