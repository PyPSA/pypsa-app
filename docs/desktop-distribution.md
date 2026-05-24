# Desktop Distribution Plan — Windows

## Goal

Ship `pypsa-app` + `snakedispatch` as a single Windows desktop application: a native executable the user double-clicks, which manages all background services and opens the UI in an embedded browser window.

No Docker. No server setup. Close-client distribution only.

---

## Prerequisites (stated, not abstracted)

These are required on the user's machine and must be documented in the installer and README:

| Requirement | Why | Install method |
|---|---|---|
| Windows 10 22H2+ or Windows 11 | Edge WebView2 is built-in on these versions | — |
| Git for Windows | snakedispatch clones workflow repos | Bundled optional installer or [git-scm.com](https://git-scm.com/download/win) |
| Pixi | snakedispatch uses Pixi to isolate Snakemake envs | `winget install prefix-dev.pixi` or bundled |
| Internet (first launch only) | uv warm-up installs Python packages on first run | — |

**WSL2 note**: Not required for the app itself. Required only if a user's Snakemake workflows use Unix shell commands (`rule: shell: "bash ..."`, GNU coreutils, etc.). Workflow authors are responsible for cross-platform compatibility. If users need Unix-only workflows, they should set up a remote snakedispatch on a Linux/WSL2 machine and configure it as an additional backend via the admin panel.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Wails desktop app  (Go + Edge WebView2)            │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Control plane (Go)                          │   │
│  │  - Prerequisite checker                      │   │
│  │  - First-launch setup (uv venv creation)     │   │
│  │  - Process manager (spawn / health / kill)   │   │
│  │  - System tray (start, stop, restart, quit)  │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  WebView ──► http://localhost:8765                  │
└─────────────────────────────────────────────────────┘
         │ spawns                │ spawns
         ▼                       ▼
┌─────────────────┐   ┌──────────────────────┐
│  pypsa-app      │   │  snakedispatch       │
│  FastAPI :8765  │──►│  FastAPI :8766       │
│  SQLite         │   │  local backend       │
│  in-memory tasks│   │  Pixi + Git on PATH  │
└─────────────────┘   └──────────────────────┘
         │
         └── serves built SvelteKit static files
```

**pypsa-app** runs in minimal mode: SQLite database, in-memory Celery fallback (no Redis, no PostgreSQL, no separate worker process).

**snakedispatch** runs with a local backend config written by the Wails app on first launch. `SNAKEDISPATCH_BACKENDS=local=http://localhost:8766` is passed to pypsa-app as an env var at startup.

---

## Project Structure

A new `desktop/` directory inside `pypsa-app`:

```
pypsa-app/
└── desktop/
    ├── main.go                 # Wails entry point
    ├── app.go                  # Control plane logic
    ├── process.go              # Subprocess management
    ├── setup.go                # First-launch warm-up / uv setup
    ├── prereqs.go              # Prerequisite detection
    ├── versions.yaml           # Pinned versions for pypsa-app and snakedispatch
    ├── wails.json
    ├── go.mod
    ├── frontend/               # Wails loading/status UI (Svelte, minimal)
    │   └── src/
    │       └── App.svelte      # Splash screen, warm-up progress, error states
    └── build/
        ├── windows/
        │   ├── installer.nsi   # NSIS script (built locally, no CI)
        │   └── icon.ico
        └── assets/
            └── uv.exe          # Bundled uv binary (windows/amd64)
```

The Wails `frontend/` here is only the **loading/status shell** (splash screen, setup progress bar, error messages). Once pypsa-app is healthy, the WebView navigates to `http://localhost:8765` and this shell is replaced by the full pypsa-app SvelteKit UI.

---

## Data Layout on Windows

All runtime data is stored under `%APPDATA%\pypsa-desktop\`:

```
%APPDATA%\pypsa-desktop\
├── venvs\
│   ├── pypsa-app\          # uv-managed Python venv
│   └── snakedispatch\      # uv-managed Python venv
├── data\                   # pypsa-app data (SQLite DB, uploaded networks)
├── snakedispatch\          # snakedispatch job data (job dirs, snkmt.db files)
├── config\
│   └── snakedispatch.yaml  # Written by Wails on first launch
└── logs\
    ├── pypsa-app.log
    └── snakedispatch.log
```

---

## Startup Sequence

```
1. Wails app launches
2. Show splash screen
3. Check prerequisites
   ├── Git in PATH?         → warn if missing, show install link
   └── Pixi in PATH?        → warn if missing, show install link
4. Check venvs exist
   └── Missing?  → run first-launch setup (see below)
5. Write snakedispatch.yaml (idempotent)
6. Spawn snakedispatch on :8766
7. Spawn pypsa-app on :8765
8. Poll /health on both until ready (timeout: 60s)
9. Navigate WebView to http://localhost:8765
```

**First-launch warm-up** (runs once, ~30–60s on first use):
```
uv venv %APPDATA%\pypsa-desktop\venvs\pypsa-app
uv pip install --python ...venvs\pypsa-app <bundled wheels>

uv venv %APPDATA%\pypsa-desktop\venvs\snakedispatch
uv pip install --python ...venvs\snakedispatch <bundled wheels>
```

Progress is streamed to the splash screen so the user sees what's happening. On subsequent launches this step is skipped entirely (sentinel file check).

---

## Python Distribution Strategy

Both apps are shipped as **pre-built wheels bundled in the installer**. Bundle size of 300–500 MB is acceptable for v1.

- No internet required after installer runs.
- Controlled versions pinned in `desktop/versions.yaml`.
- uv installs from local paths during first-launch warm-up: `uv pip install pypsa_app-X.Y.Z-py3-none-any.whl`
- The installer places wheels in `%PROGRAMFILES%\pypsa-desktop\wheels\`.
- Wheels are built manually on a Windows machine and committed alongside the installer script. No CI pipeline in v1.

> **Future:** If bundle size becomes a concern, switch to PyPI download during warm-up (deferred install). The warm-up UI already handles progress display, so the transition is a one-line change in `setup.go`.

For updates: ship a new installer. No in-app update mechanism in v1.

---

## Installer

Built with **NSIS** (Wails' recommended Windows installer toolchain). The `.nsi` script lives in `desktop/build/windows/`.

The installer bundles:
- `pypsa-desktop.exe` (the Wails binary)
- `uv.exe` (copied to `%PROGRAMFILES%\pypsa-desktop\`)
- Pre-built `.whl` files for both Python apps and their dependencies
- `appicon.ico`, EULA, README

The installer optionally launches Git for Windows and Pixi installers if not detected (user can skip).

**Built locally**: Installer is built manually on a developer Windows machine using NSIS. No GitHub Actions pipeline in v1.

**Code signing**: Required to avoid Windows SmartScreen "unknown publisher" block. Use a code signing certificate for production releases.

---

## Implementation Phases

### Phase 0 — Validation spike (do this first, ~2 days)

Before writing any Wails code, validate the runtime stack on a real Windows machine or VM.

- [ ] Run `pypsa-app serve` in minimal mode (SQLite, no Redis) on Windows natively
- [ ] Run `snakedispatch` with local backend on Windows, submit a simple Pixi-based workflow
- [ ] Confirm Pixi installs and runs workflows on Windows without WSL2
- [ ] Confirm the pypsa-app ↔ snakedispatch integration works end-to-end

If Snakemake workflows fail on Windows during this spike, document which types fail and add them to the prerequisite warning (WSL2 needed for Unix-shell workflows).

### Phase 1 — Wails shell (~3 days)

- [ ] `desktop/` project: `wails init`, configure Go module
- [ ] Minimal splash screen frontend (SvelteKit or plain HTML): status text, progress bar, error view
- [ ] WebView navigation: splash → app URL once healthy
- [ ] System tray: Show window, Quit
- [ ] Basic port conflict detection (log and abort with message if :8765/:8766 are taken)

### Phase 2 — Process management (~3 days)

- [ ] `process.go`: spawn subprocess, capture stdout/stderr to rotating log file, detect exit
- [ ] Health polling: GET /health on both services, retry with backoff, timeout
- [ ] Graceful shutdown: SIGTERM to children, wait up to 5s, then SIGKILL
- [ ] Crash recovery: restart a dead sidecar up to 3 times before surfacing error to user
- [ ] Pass correct env vars to pypsa-app:
  - `DATABASE_URL=sqlite:///%APPDATA%\pypsa-desktop\data\pypsa-app.db`
  - `DATA_DIR=%APPDATA%\pypsa-desktop\data`
  - `SNAKEDISPATCH_BACKENDS=local=http://localhost:8766`
  - `ENABLE_AUTH=false`
  - `BASE_URL=http://localhost:8765`

### Phase 3 — First-launch setup (~3 days)

- [ ] `prereqs.go`: check Git and Pixi in PATH, return structured results
- [ ] `setup.go`: detect venvs, run uv to create and populate them from bundled wheels, stream progress to frontend
- [ ] Splash screen shows per-step warm-up progress ("Installing pypsa-app... 47%")
- [ ] On error: show actionable message (e.g. "Git not found. Install from git-scm.com and restart.")
- [ ] Mark setup complete in a sentinel file so it's skipped on subsequent launches

### Phase 4 — snakedispatch config generation (~1 day)

- [ ] Write `snakedispatch.yaml` to `%APPDATA%\pypsa-desktop\config\` on first launch
- [ ] Local backend config: `scratch_dir`, `pixi_path` (resolved from PATH), `poll_interval: 5`
- [ ] Pass config path to snakedispatch via env var or CLI arg

### Phase 5 — Installer (~2 days)

- [ ] `desktop/build/windows/installer.nsi`: NSIS script
- [ ] Bundle exe, uv.exe, wheels directory (built manually, no CI)
- [ ] Optional: detect Git/Pixi absence, prompt to install during setup wizard
- [ ] Uninstaller removes `%PROGRAMFILES%\pypsa-desktop\` (not `%APPDATA%` — preserve user data)
- [ ] Produce `pypsa-desktop-setup-vX.Y.Z.exe` from local build

### Phase 6 — Polish & release (~2 days)

- [ ] Code signing setup (self-signed for internal distribution, CA-signed for wider release)
- [ ] Windows Event Log or toast notifications for crash events
- [ ] "About" menu: shows pypsa-app version, snakedispatch version, Python version
- [ ] Smoke test checklist on a clean Windows 11 VM

---

## Decisions

| # | Decision |
|---|---|
| 1 | **Wheel build**: Built manually on a developer Windows machine. No GitHub Actions CI in v1. |
| 2 | **Version pinning**: `desktop/versions.yaml` pins both `pypsa-app` and `snakedispatch` versions for each installer release. Go code reads this file at build time. |
| 3 | **Local backend in admin**: The bundled snakedispatch appears as **"local (managed)"** — visible but not editable. Users can freely add additional remote backends via the admin panel. |
| 4 | **Authentication**: `ENABLE_AUTH=false` for all desktop installs. Single shared instance per machine. Acceptable for v1 close-client distribution. |
| 5 | **Dependency bundle**: Ship pre-built wheels (300–500 MB) in the installer. No internet required after install. If bundle size becomes a concern in a future release, switch to first-launch warm-up via PyPI download — the warm-up UI already supports this flow. |
