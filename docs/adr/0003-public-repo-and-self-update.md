# 0003 - Public repo + GitHub Releases self-update

## Status
Accepted

## Context
The exe must update itself "whenever you run it, if there's a new version." Two
shapes were possible: a **private** repo (matches the TrueNAS fleet default) or a
**public** one.

A private repo's release assets require an authenticated GitHub token to
download. That token would have to be embedded in the distributed exe - a real
secret-leak risk, and it still wouldn't be a homelab/TrueNAS deployment anyway.

## Decision
Make the repo **public**. The running exe checks the public Releases API on
launch, with **no embedded token**, and self-updates if a newer version exists.

Flow (`updater.py`, only when running as a frozen exe):
1. `GET /repos/<repo>/releases/latest` (6s timeout).
2. Compare the release tag to the baked-in version (`is_newer`).
3. If newer, download the `KidComputer.exe` asset next to the current exe.
4. Write a small batch script that waits for this process to exit, moves the new
   exe over the old one, relaunches it, and deletes itself; then exit.

Versioning: `VERSION` holds `MAJOR.MINOR` (`1.0`); CI sets the patch to the
workflow run number, so every push to `main` yields a strictly increasing
`1.0.<run_number>` - monotonic, which is exactly what the comparison needs.

## Consequences
- Frictionless, tokenless auto-update.
- **No secrets may ever be committed** to this repo (enforced by it being public
  and by `.gitignore`). The repo contains only code - no server addresses, keys,
  or paths (unlike the private homelab repos).
- Update is **fail-open**: any network/HTTP/parse error logs WARNING and the
  current build keeps running.
- Rollback = publish a higher version with the old code (versions only go up).
