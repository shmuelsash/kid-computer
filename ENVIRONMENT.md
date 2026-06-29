# Environment & tooling — keep it ISOLATED

The dev machine has six Python installs and no version manager. NEVER depend on
global `python`/`pip` or system PATH — whichever one PATH resolves to is luck and
will be the wrong version. Keep EVERYTHING per-project and isolated.

- **Python — always `uv`** (installed). NEVER run bare `python`, `pip`, `poetry`,
  or `conda`. At the start of Python work: `uv init` if there's no `pyproject.toml`,
  pin the version (`uv python pin 3.12`, installing it with `uv python install 3.12`
  if missing), then `uv sync`. Add deps with `uv add <pkg>` (never `pip install`).
  Run everything through the env: `uv run <cmd>` (e.g. `uv run python …`,
  `uv run pytest`). The project-local `.venv/` is the only environment — never
  install globally.
- **Node — project-local only.** `npm install` into the local `node_modules/`;
  NEVER `npm install -g`. Run tools via `npx <tool>` or `package.json` scripts
  (`npm run <script>`). Declare a required version in `"engines"` and say so —
  don't silently use whatever PATH gives.
- **Never modify system PATH / env vars to "fix" a problem.** Missing tool →
  install it project-locally or via `uv`/`npx`, not globally.
- **Verify before building** and report in plain English: print `uv run python
  --version` and/or `node --version` and state exactly what will be used.
- **One project = one isolated environment.** On "command not found" / wrong
  version / PATH error: STOP, explain the cause plainly, fix it the isolated way
  above — never paper over it with a global install.
