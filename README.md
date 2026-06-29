# Kid Computer

A full-screen **"baby smash"** app for Windows. Launch it before you hand the
laptop to a toddler: it **locks out the keyboard** so no key combination can
trigger emails, lock the account, or break anything - and turns every key press
and mouse click into **shapes, fireworks, colors, pop-up windows, and happy
sounds**. The only way out is a secret grown-up combo.

> **Exit:** hold **Ctrl + Alt + Q** together for 2 seconds. An on-screen hint
> always shows this. Releasing early cancels.

## What it does

- **Locks the escape routes.** A low-level Windows keyboard hook swallows the
  Windows key, Alt+Tab, Alt+F4, Alt+Esc, Ctrl+Esc, and the context-menu key.
  Ordinary keys still flow through to drive the fun.
- **Reacts to everything.** Each key spawns a big spinning shape and the pressed
  letter/number, with a cheerful musical note. Mouse clicks set off fireworks +
  a chime. Moving the mouse leaves a sparkle trail. Little "windows" pop open and
  closed, the background gently shifts color, and there's always something moving
  even when no one's touching it.
- **Toddler-tuned.** Big bold shapes, well-saturated colors, soft (non-strobing)
  color washes, and a pentatonic sound bank so random mashing always sounds nice.
- **Self-updating.** When you run the `.exe`, it checks GitHub for a newer build
  and updates itself automatically. No app store, no manual download.

## What it can and can't lock (please read)

A normal Windows program (one that isn't an enterprise kiosk lockdown) **can**
block all the shortcuts above - which covers essentially everything a small child
will hit. It **cannot** block two keys, by Windows design:

- **Ctrl + Alt + Del** - a hardware-level "secure attention" key the OS always
  reserves. It just shows the blue secure screen; press **Esc** to go back. It
  can't send an email or break anything.
- **Win + L** - locks the workstation (you log back in normally).

Truly disabling those would require Group Policy / kiosk-mode lockdown of the
whole PC, which is out of scope for a simple app. In practice they're not keys a
toddler stumbles into, and neither causes harm.

## Install (for a parent, no coding needed)

1. Go to the repo's **Releases** page and download the latest **`KidComputer.exe`**.
2. Double-click it. (Windows SmartScreen may warn about an unsigned app the first
   time - choose **More info -> Run anyway**.)
3. It goes full-screen and locks the keyboard. Let your child play.
4. To quit: hold **Ctrl + Alt + Q** for 2 seconds.

The next time you run it, if a newer version exists it updates itself first, then
launches.

## Develop

Requires [uv](https://docs.astral.sh/uv/). All Python is isolated in a local
`.venv` - nothing is installed globally.

```sh
uv sync              # create the env and install deps
make dev             # run in a window (Ctrl+Alt+Q to quit) - or: ./dev.ps1
make check           # ruff format + lint + mypy (the CI gate)
make test            # pytest (headless)
make build           # build dist/KidComputer.exe locally - or: ./build.ps1
```

On Windows without `make`, use the scripts: `./dev.ps1`, `./build.ps1`, or
`uv run python -m kidcomputer`.

### Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `KIDCOMPUTER_FULLSCREEN` | `1` | `0` = windowed (handy for dev) |
| `KIDCOMPUTER_SOUND` | `1` | `0` = mute |
| `KIDCOMPUTER_AUTO_UPDATE` | `1` | `0` = skip the update check |
| `EXIT_HOLD_SECONDS` | `2.0` | How long the exit combo must be held |

Logs go to stdout and to a rotating file at
`%LOCALAPPDATA%\KidComputer\kid-computer.log`.

## How shipping works

```
push to main ─▶ checks (ruff/mypy/pytest)  ──fail──▶ ✗ no exe built
                   │ pass
                   ▼
                build exe (PyInstaller, Windows) with version + git SHA baked in
                   │
                   ▼
                publish GitHub Release  v1.0.<run_number>  + KidComputer.exe
                   │
                   ▼
        running exe checks Releases on launch ─▶ self-updates if newer
```

Every push to `main` produces a new release `v1.0.<run_number>` (monotonic, so
the updater always knows what's newer). Version, git SHA, and build time are baked
into the exe and shown in the startup log and the small About line on screen.

To cut a release: merge to `main`. To bump the human-facing major/minor, edit the
`VERSION` file (`1.0`).

## Architecture

| Module | Responsibility |
|---|---|
| `app.py` | Main loop; wires everything; **always releases the lock in `finally`** |
| `keyboard_lock.py` | Windows `WH_KEYBOARD_LL` hook; pure `should_block()` decision |
| `exit_watcher.py` | Pure hold-combo timer (Ctrl+Alt+Q), injectable clock |
| `scene.py` | Turns input into effects + sound; background, hint, exit ring |
| `effects.py` | Shapes, glyphs, fireworks, sparkles, pop-up windows |
| `audio.py` | numpy-synthesized pentatonic notes + chime |
| `updater.py` | GitHub Releases check + download + self-replace |
| `config.py` / `logging_setup.py` / `buildinfo.py` | settings, logging, provenance |

Design decisions are recorded in [docs/adr/](docs/adr/). The engineering
standards this repo follows live in
[ENGINEERING-BASELINE.md](ENGINEERING-BASELINE.md) (the web-app security/frontend
baselines intentionally don't apply - see
[ADR 0001](docs/adr/0001-windows-desktop-deviation.md)).

## License

MIT - see [LICENSE](LICENSE).
