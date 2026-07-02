# Claude Code

This repo's agent instructions live in [`AGENTS.md`](AGENTS.md) — the tool-agnostic
standard read by Claude Code, Codex, Cursor, and other agents. Keeping one source of
truth avoids drift between per-tool files.

The line below imports `AGENTS.md` so Claude Code loads the full content automatically
every session. **Edit `AGENTS.md`, not this file.**

@AGENTS.md
