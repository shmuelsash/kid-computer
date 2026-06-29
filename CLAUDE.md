# Kid Computer - project guardrail

A full-screen Windows "baby smash" app for a toddler: it locks the keyboard so a
small child can mash keys safely, turning every press/click into shapes,
fireworks, colors, and happy sounds. The only way out is holding **Ctrl+Alt+Q**
for 2 seconds. It builds to a single `.exe` and **self-updates from GitHub
Releases**.

## How this differs from the homelab baseline (read this first)

This is a **Windows desktop app**, not a Dockerized web service. The homelab
`SECURITY-BASELINE.md` (auth, sessions, CSRF, containers) and
`FRONTEND-BASELINE.md` (web tokens, mobile/desktop parity) **do not apply** -
there is no server, no auth, no browser, no network input surface. See
[docs/adr/0001-windows-desktop-deviation.md](docs/adr/0001-windows-desktop-deviation.md).

The **`ENGINEERING-BASELINE.md`** and **`ENVIRONMENT.md`** rules **do** apply and
are carried over:

- **Isolated env** - all Python via `uv` + local `.venv`. Never global `python`/`pip`.
- **One task-runner interface** - `make dev/check/test/build` (mirrored by `dev.ps1`).
- **Blocking CI gate before build** - `ruff format`, `ruff check`, `mypy`,
  `pytest` must pass before the release workflow builds/publishes the exe.
- **Readable, DRY, shallow** - guard clauses, named conditions, ruff `C90`
  complexity gate (max 10).
- **Structured logging** (global `~/.claude/LOGGING.md`) - `logging` module,
  `LOG_LEVEL` env, stdout + rotating file, startup line with version + provenance.
- **Version & build provenance baked at build time** - `1.0.<run_number>` + git
  SHA + build time, written into `kidcomputer/_generated_buildinfo.py` by CI,
  surfaced in the startup log and the on-screen About text.
- **Tests gate the build** - the safety-critical core (exit combo timing,
  keyboard block decisions, version comparison, audio contract) is unit-tested.

## Safety invariants - DO NOT REGRESS

- **The keyboard lock must always be released on exit.** Every exit path runs
  through the `finally` block in `app.main`. Never add a return/raise that skips it.
- **The exit combo must keep working** - `Ctrl+Alt+Q` held for `EXIT_HOLD_SECONDS`.
  An always-visible on-screen hint tells the grown-up how to get out.
- **Auto-update must fail open** - a network/HTTP error logs WARNING and the
  current build keeps running; it never blocks the child's session.
- **Never swap in an unverified exe.** Before replacing the running exe, the
  download must be complete (Content-Length match) and pass `_is_valid_exe`
  (exact published asset size + PE 'MZ' magic). The relaunch batch waits for the
  old process to exit by PID before the atomic same-folder move. A truncated swap
  once bricked an install ("Failed to load Python DLL") - do not regress this.
- **Every WinAPI ctypes call declares `argtypes` + `restype`.** Without them,
  ctypes truncates 64-bit handles/`LRESULT` to 32 bits on Win64 and the keyboard
  hook silently fails to install (the keys-not-blocked bug). The `_HOOKPROC`
  return type must be `LRESULT` (`c_ssize_t`), never `c_long`.
- **DPI awareness is declared before any window is created** (`make_dpi_aware()`
  first in `main`), or Windows reports a scaled resolution and the UI is blurry.
- **`.ps1` files are ASCII-only** (house rule) - no em dashes or curly quotes.

## What can't be blocked (by Windows design)

A user-mode app cannot block **Ctrl+Alt+Del** or **Win+L**. These are OS safety
features; neither can break anything (Esc backs out of the Ctrl+Alt+Del screen).
Don't try to "fix" this with registry/Group-Policy hacks unless explicitly asked.

## Layout

- `kidcomputer/` - package: `app` (loop), `display` (DPI + multi-monitor),
  `keyboard_lock`, `exit_watcher`, `scene`, `effects`, `audio`, `updater`,
  `config`, `logging_setup`, `buildinfo`.
- `tests/` - pytest, headless (SDL dummy drivers).
- `.github/workflows/` - `ci.yml` (gate) and `release.yml` (gate -> build -> release).

@ENVIRONMENT.md
