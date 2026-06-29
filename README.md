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
  Windows key (and every Win+<key> combo, including Win+Tab/Win+D), Alt+Tab,
  Ctrl+Alt+Tab, Alt+F4, Alt+Esc, Ctrl+Esc, Ctrl+Shift+Esc, and the context-menu
  key. Ordinary keys still flow through to drive the fun.
- **Covers every screen, at full resolution.** Runs DPI-aware (sharp, native
  resolution - no blurry upscaling) and spans a borderless top-most window across
  **all connected monitors**, so a second screen is covered too.
- **Reacts to everything.** Keys spawn glowing shapes and the pressed
  letter/number with a cheerful pentatonic note; clicks set off fireworks + a
  chime; the mouse leaves a sparkle trail; soft bokeh and ripples drift in the
  background. All anti-aliased with a gentle bloom on a deep gradient.
- **Three age modes** (switchable in Settings): **Toddler - Bubbles & Booms**
  (big, slow, simple); **Preschool - Letters & Friends** (letters/numbers,
  counting dots, smiley shapes); **Early school - Cosmic Maker** (kaleidoscope
  symmetry, constellations, word building).
- **Three themes** - Aurora, Candy, Minimal - plus an **effect-intensity** slider,
  a **sound** toggle, and a **log-level** selector. All in a settings card opened
  by the auto-hiding gear (top-right), and **saved between runs**.
- **Self-updating, visibly.** On launch it shows a "Checking for updates..." /
  "Downloading vX - NN%" splash, then updates itself from GitHub and relaunches.
  No app store, no manual download.

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
4. Move the mouse to the **top-right gear** to open Settings (age mode, theme,
   intensity, sound). Choices are remembered next time.
5. To quit: hold **Ctrl + Alt + Q** for 2 seconds (or use the Exit button in Settings).

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
| `LOG_LEVEL` | `INFO` | Initial level (`DEBUG`/`INFO`/`WARNING`/`ERROR`); also changeable live in Settings |
| `KIDCOMPUTER_FULLSCREEN` | `1` | `0` = windowed (handy for dev) |
| `KIDCOMPUTER_SOUND` | `1` | Initial mute default; also toggled in Settings |
| `KIDCOMPUTER_AUTO_UPDATE` | `1` | `0` = skip the update check |
| `EXIT_HOLD_SECONDS` | `2.0` | How long the exit combo must be held |

User-facing preferences (age mode, theme, intensity, sound, log level) are
changed in the in-app Settings card and persisted to
`%LOCALAPPDATA%\KidComputer\settings.json`. Logs go to stdout and to a rotating
file at `%LOCALAPPDATA%\KidComputer\kid-computer.log`.

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
| `app.py` | Main loop + update splash; wires everything; **always releases the lock in `finally`** |
| `display.py` | DPI awareness + borderless window spanning all monitors; primary-monitor `ui_rect` |
| `keyboard_lock.py` | Windows `WH_KEYBOARD_LL` hook; pure `should_block()` decision |
| `exit_watcher.py` | Pure hold-combo timer (Ctrl+Alt+Q), injectable clock |
| `scene.py` | Per-age-mode spawning; themed background, hint, gear, AA exit ring |
| `effects.py` | Glowing shapes, glyphs, fireworks, sparkles, ripples, bokeh, friends, constellation |
| `render.py` | numpy gradient + bloom-glow sprites + anti-aliased ring |
| `theme.py` / `modes.py` | Theme palettes (Aurora/Candy/Minimal) and age-mode behavior configs |
| `settings_panel.py` | The gear's glass settings card (hit-testing + live apply) |
| `audio.py` | numpy-synthesized pentatonic notes + chime |
| `updater.py` | Threaded GitHub Releases check + download (progress) + self-replace |
| `config.py` / `logging_setup.py` / `buildinfo.py` | settings store, logging, provenance |

Design decisions are recorded in [docs/adr/](docs/adr/). The engineering
standards this repo follows live in
[ENGINEERING-BASELINE.md](ENGINEERING-BASELINE.md) (the web-app security/frontend
baselines intentionally don't apply - see
[ADR 0001](docs/adr/0001-windows-desktop-deviation.md)).

## License

MIT - see [LICENSE](LICENSE).
