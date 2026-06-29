# 0001 - Windows desktop app deviates from the homelab web-app baseline

## Status
Accepted

## Context
The repo-starter-kit baselines target single-admin **web apps in Docker on
TrueNAS**: auth (setup -> login -> Settings), sessions, CSRF, non-root
containers, `/healthz`, mobile/desktop web views, and a GHCR -> TrueNAS deploy
pipeline. Kid Computer is none of those - it is a single-user **Windows desktop
application** that compiles to one `.exe`, runs full-screen on a laptop, takes no
network input, stores no user data, and distributes via GitHub Releases.

## Decision
Apply the parts of the baseline that are about *engineering quality* and drop the
parts that assume a web service:

**Kept (ENGINEERING-BASELINE.md + ENVIRONMENT.md):** uv-isolated env, one
`make`-style task runner, blocking CI gate (format/lint/types/tests) *before* the
build, readable/DRY/shallow code with a complexity gate, structured logging with
`LOG_LEVEL`, version + git-SHA + build-time provenance baked at build time and
surfaced at runtime, tests gating the build, README + ADRs, committed lockfile +
Dependabot.

**Dropped as not applicable:** web auth/sessions/CSRF (no server, no login),
container hardening (no container), `/healthz` + compose healthcheck (no
service), and the web FRONTEND-BASELINE mobile/desktop parity + design-token
rules (no web UI - it's a pygame canvas).

**Repo is public** (not private like the TrueNAS fleet): the private rule exists
because self-hosted runners on the NAS can run fork-PR code as `admin`. This repo
uses GitHub-hosted runners only and ships no secrets, and a public repo lets the
distributed exe self-update with no embedded token. See
[0003-public-repo-and-self-update.md](0003-public-repo-and-self-update.md).

## Consequences
- The security surface shrinks to: don't leave the keyboard locked, fail-open
  updates, ASCII-only scripts. These are captured as invariants in `CLAUDE.md`.
- A future networked feature (telemetry, remote config) would reintroduce parts
  of the security baseline and needs its own ADR.
