# Engineering Baseline

Every app in this homelab must meet this baseline — UI apps and CLI / script apps
alike. It standardizes how repos are organized, tested, and shipped so the fleet
stays consistent and changes don't regress quality. **Behavior over tooling:** where
a stack differs (Python / `uv`, Node, Go), keep the **intent** identical; only the
commands change.

**Apply it as you write, not after.** The standard shapes the code on the first pass —
the **Code quality** CI gate, audits, and PR checklist are backstops that should rarely
fire, not where problems get found.

In **audit mode**, list every gap with `file:line` + a concrete fix, and run the
checks (lint, types, tests, build) before finishing.

## 1. Project structure
- Predictable layout: source in one place, **tests beside the code or under `tests/`**,
  config at the root, docs in `README.md`. No business logic in entrypoints.
- **One app = one isolated environment** (see ENVIRONMENT.md): `uv` + `.venv` for
  Python, local `node_modules` for Node. Never global.
- Secrets stay out of the tree: `.env` gitignored, `.env.example` committed with
  placeholders (matches SECURITY-BASELINE → Secrets).

## 2. Task runner & local dev
One interface to build, run, check, and test — identical verbs in every repo, whatever
the stack. This is what keeps the fleet uniform and the CI gate portable.
- **Standard verbs** — a `Makefile` (wrapping the stack's `npm` scripts / `uv` commands)
  exposing: `make dev` (run locally), `make check` (format + lint + types + complexity +
  duplication — exactly what the CI gate runs), `make test`, `make build`. CI just calls
  `make check` / `make test`, so **CI and your machine run the same thing**.
- **One-command local run — `dev.ps1`** (copy `templates/dev.ps1`). A single command that
  builds the **real image**, starts it via `docker compose`, **streams all logs in one
  window**, and **auto-opens the browser** once the app answers — so you verify the actual
  artifact end-to-end *before* pushing. Runs with `LOG_LEVEL=DEBUG`; `Ctrl+C` stops and
  cleans up. (`dev.cmd` is a double-click shim for true one-click.)
- **Parity with prod:** local dev uses the same `docker-compose.yml` + `Dockerfile` that
  deploy to TrueNAS, so "works on my machine" means "works in the container." Native
  hot-reload servers are fine for inner-loop speed, but the **pre-push check is the
  containerized run**.

## 3. Linting, formatting & types — enforced, not optional
- **Format in CI**, no debates: Python `ruff format` (via `uv`), JS/TS `prettier`,
  Go `gofmt`. A formatting diff fails CI.
- **Lint** with autofix where safe: `ruff` (Python), `eslint` (JS/TS),
  `go vet` / `golangci-lint` (Go).
- **Strict types:** TS `strict: true` (no implicit `any`); Python type hints + a
  checker (`mypy` / `pyright` via `uv`); Go is typed. New code doesn't bypass the
  checker — a `# type: ignore` / `any` needs a reason in a comment.

## 4. Code quality — readable, DRY, shallow
Code is read far more than written. Optimize for the next person (often you, or an
agent) understanding it fast.

**Simplicity & reuse — no bloat**
- **Reuse before adding** — look for an existing function / component before writing a
  new one; when the same logic shows up a third time, extract a shared helper instead of
  copy-pasting. Don't over-abstract for a hypothetical future either (YAGNI).
- **Delete dead code** — unused functions, vars, imports, files, commented-out blocks.
  Git history is the archive; nothing kept "just in case." Lint catches the small stuff
  (`no-unused-vars`, ruff `F401`).
- **Small, single-responsibility units** — a function does one thing; a module owns one
  concern. If you can't name it without "and," split it.

**Readability & comments**
- **Intention-revealing names** — `isExpired`, `pendingUploads`, not `x`, `tmp`,
  `data2`. A good name removes the need for a comment.
- **Comments explain WHY, not WHAT** — the code is the *what*. Comment the non-obvious:
  business rules, gotchas, workarounds, a link to the issue / SHA. (The existing docs
  model this — "Don't seed login passwords via env…".)
- **Keep comments true** — update or delete them with the code; a stale comment is worse
  than none.

**Shallow control flow — avoid deep nesting**
- **Guard clauses / early returns** instead of nested `if / else` pyramids: handle the
  edge cases up front and return, so the happy path stays flat and un-indented.
- **Name your conditions** — hoist a complex boolean into a well-named variable or a
  small predicate function. `const canDeploy = testsPassed && !isDraft && hasApproval`
  reads in English; `if (a && b && (c || d) && !e)` does not.
- **Tables over long chains** — replace a long `if / else-if` (or `switch`) on a value
  with a lookup map / dict where it fits.
- Aim for **shallow nesting (~3 levels max)** and few branches per function.

**These are hard gates, not advice — the build fails first.** **Linting/format/types**,
**Code quality**, and **Testing** run as a **blocking CI check _before_ the image is
built** (the deploy workflow's `checks` job; `build` is `needs: checks`). The gate
covers: format, lint, **strict types**, **complexity / nesting** (eslint `complexity` +
`max-depth`; ruff `C901`), **duplicate code** (`jscpd`, fail on clones), and the gated
tests (**Testing**). Any failure → the image is **never built or pushed**, so a
regression can't reach TrueNAS. Enforce the same rules **earlier and locally**: editor
**format-on-save** + the eslint/ruff extension (violations surface as you type), and a
**pre-commit hook** (fails before it's even committed). CI is the last line of defense,
not the first.

## 5. Testing — critical paths are gated
- **The auth flow is always tested** — setup → login (incl. rate-limit + generic
  error) → credential change (re-auth + other-session invalidation). This guards the
  security baseline directly.
- **Each app's core happy path is tested** — the one workflow the app exists for
  (e.g. receipt upload → parse; a full sync run).
- **These must pass in CI before the TrueNAS runner deploys.** A red test blocks the
  deploy, not just the PR.
- Framework per stack: `pytest` via `uv`, `vitest` / `jest`, `go test`. Tests are
  deterministic — no live network, fake the clock / IO.

## 6. Health & config — fail closed, observable
- Expose **`/healthz`** (or `/health`) returning 200 + app version + a quick check of
  critical deps (e.g. DB reachable). Wire it into the compose **`healthcheck:`** so
  restarts and the reverse proxy can tell live from dead.
- **Validate required config at startup** — a missing / invalid required value
  (signing key, DB path, required secret) **fails closed** at boot with a clear log
  line, never a silent default (matches SECURITY-BASELINE → Secrets).
- **Startup log line** (matches LOGGING.md): version, config source, bound
  address/port, active log level. `LOG_LEVEL` env controls verbosity; UI apps also
  expose a log-level selector (FRONTEND-BASELINE → Information architecture, Advanced).

## 7. Data safety — never lose or corrupt data
Your apps hold data you can't recreate (receipts, bills, sync state) in a persisted
volume. This is the one failure class that's unrecoverable — treat it that way.
- **Migrations, never destructive edits.** Schema changes ship as **versioned,
  forward-only migrations** that run at startup and **preserve existing data** — never a
  manual `ALTER`/drop, never "delete the DB and let it recreate." A new image must
  upgrade an old DB in place; test the migration against a copy of real data.
- **Back up before you migrate.** A deploy that runs a migration snapshots / copies the
  DB first, so a bad migration can be rolled back.
- **Backups are documented and restorable.** State exactly what to back up (the data
  volume / DB file) and prove the **restore path works** — an untested backup isn't one.
  TrueNAS snapshots may be the mechanism, but the README says what + how to restore.
- **Graceful shutdown.** Handle `SIGTERM` — finish in-flight work and close the DB
  cleanly — so a deploy-restart never corrupts data mid-write. For SQLite, enable **WAL
  mode** and checkpoint before exit.

## 8. Versioning & build provenance
Every app must answer "**what build is this, and where did it come from?**" at runtime —
without guessing.
- **Source of truth:** a `MAJOR.MINOR.PATCH` version (committed `VERSION` file or git
  tag) **plus the git commit SHA** the build came from. On a deploy-from-`main` fleet the
  short SHA is the real build id; the version is the human label.
- **Bake it at build time — never compute at runtime.** The GitHub Actions build passes
  the values as build args; the image records them as **OCI labels**
  (`org.opencontainers.image.version` / `.revision` / `.created` / `.source`) and as
  runtime values (env vars or a generated `version.json`): `APP_VERSION`, `GIT_SHA`
  (`${{ github.sha }}`), `GIT_REF` / channel, `BUILD_TIME` (ISO-8601 UTC).
- **Surface the same values in three places:**
  1. **Startup log** (LOGGING.md) — the boot line includes version + short SHA + build time.
  2. **`/healthz`** (**Health & config**) — returns `{ version, commit, builtAt }` for monitoring / the proxy.
  3. **Settings → Advanced** (FRONTEND-BASELINE → Information architecture) — an **About**
     block: version, short SHA (linked to the GitHub commit when the repo URL is known),
     build date, channel.
- **Bump `VERSION` (or the tag) on meaningful releases;** the SHA changes every build
  automatically, so provenance is never stale.

## 9. Dependencies
- **Commit lockfiles** — `uv.lock`, `package-lock.json`, `go.sum`. Builds are
  reproducible; nothing floats to a new version at deploy time.
- **Pin the runtime:** Python via `uv python pin`, Node via `"engines"`, Go via
  `go.mod`.
- **Automated updates:** a Dependabot / Renovate config opens dependency-bump PRs; CI
  + the gated tests (**Testing**) decide whether they merge.

## 10. Git & pull-request workflow
- **Branch naming:** `feat/…`, `fix/…`, `chore/…`, `docs/…` off `main`.
- **Commits:** imperative, scoped to one logical change. When a change touches
  auth / sessions / secrets / Dockerfile, say so in the message ("Security baseline: …").
- **PR checklist** (`.github/pull_request_template.md`): security baseline not
  regressed · tests pass · lint + types clean · mobile **and** desktop both updated
  (UI changes) · docs updated. Squash-merge; never force-push `main`.
- **Branch hygiene:** enable **"Automatically delete head branches"** so merged PR
  branches remove themselves (`gh repo edit <owner>/<repo> --delete-branch-on-merge`),
  and set `git config --global fetch.prune true` so stale remote-tracking refs are pruned
  every fetch. Squash-merged branches aren't detected locally (`git branch -d` can't tell) —
  prune them periodically (e.g. `Sync-Repos.ps1 -PruneGone`), never let them pile up.

## 11. Documentation & decisions
- **README is required** and documents: what the app is, how to run / build it locally
  (the actual `uv` / `npm` commands, and `./dev.ps1` to run the container), how it
  deploys, and **the auth flow** for that app.
- **ADRs for non-obvious decisions:** a short `docs/adr/NNN-title.md` (context /
  decision / consequences). One paragraph is fine — the point is future-you knows
  *why*.
- Keep the `AGENTS.md` baseline block in every repo (with the `CLAUDE.md` stub that
  imports it) so the rules auto-load each session.

---
*Companion to SECURITY-BASELINE.md and FRONTEND-BASELINE.md. Defaults you may tune per
app: the exact lint / type tools, the nesting-depth target, the ADR location, the
branch-name prefixes. The auth-flow test and the deploy-blocking CI gate are not optional.*
