# Desktop Distribution Plan — Windows

> **Current dev platform**: macOS M4. Windows is the distribution target.
> Daily iteration runs both services manually with `uv` — no Wails involved.
> `wails build` / `wails dev` are only used when testing the Wails shell itself.

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
| Internet | Not required — Python packages are bundled in the installer | — |

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

## Development Workflow (macOS / Linux)

For daily iteration you do **not** need Wails at all. Run both services directly with `uv` and access the UI in a browser.

### One-time setup

```bash
# pypsa-app — install deps into the project venv
cd /path/to/pypsa-app
uv sync

# snakedispatch — install deps into its project venv
cd /path/to/snakedispatch
uv sync
```

### Run services manually

**Terminal 1 — pypsa-app** (from `pypsa-app` repo root)
```bash
uv run pypsa-app serve --host 127.0.0.1 --port 8000 --data-dir ./data
```

**Terminal 2 — snakedispatch** (from `snakedispatch` repo root)
```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**Terminal 3 — SvelteKit dev server** (hot reload; skip if testing static build)
```bash
cd frontend/app
pnpm run dev
# UI at http://localhost:5173  (API proxied to :8000)
```

Open `http://localhost:8000` (static build) or `http://localhost:5173` (dev server with hot reload).

> **Note**: dev ports (8000/8001) differ from the Wails production ports (8765/8766). This is intentional — running both at the same time won't conflict.

> **Version discrepancy between `uv run` and `wails dev`**: `setuptools_scm` freezes the version number at install time by counting git commits since the last tag (e.g. `v0.1.0a1.dev78`). The project `.venv` (used by `uv run`) and the Wails-managed venv (`~/Library/Application Support/pypsa-desktop/venvs/pypsa-app`) are installed independently, so they show different `devN` numbers if installed at different commits. The running code is identical — the number is cosmetic. To sync the project venv to the current commit:
> ```bash
> uv sync --reinstall-package pypsa-app
> ```

### After changing frontend code

```bash
# Rebuild static files into src/pypsa_app/backend/static/app/
cd frontend/app && pnpm run build
# Then restart pypsa-app (Terminal 1) to serve the new files
```

### When to use `wails dev`

Only when you are working on the **Wails shell** itself (splash screen, startup sequence, system tray). It is not needed for pypsa-app or frontend changes.

```bash
cd desktop
wails dev
```

`wails dev` will detect the local `pypsa-app` source, install it into a managed venv under `~/Library/Application Support/pypsa-desktop/`, and spawn both services. Because no sentinel file is written in dev mode (`setup.go`), it reinstalls `pypsa-app` from local source on every launch using `uv pip install --reinstall-package pypsa-app`.

> **Stale venv from a previous run?** If an old venv exists from before this behaviour was introduced, delete the sentinel to force a clean reinstall:
> ```bash
> rm ~/Library/Application\ Support/pypsa-desktop/venvs/setup_complete
> ```

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
        │   ├── icon.ico
        │   ├── uv.exe              # Bundled uv binary (gitignored, downloaded manually)
        │   ├── wheels/
        │   │   ├── pypsa-app/      # win_amd64 wheels (gitignored, collected manually)
        │   │   └── snakedispatch/  # win_amd64 wheels (gitignored, collected manually)
        │   └── installer/
        │       └── project.nsi     # NSIS script (tracked in git)
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

Progress is streamed to the splash screen so the user sees what's happening. On subsequent launches this step is skipped entirely via a sentinel file (`venvs/setup_complete`).

**Sentinel behaviour differs by mode:**
- **Production** (bundled wheels): sentinel written after first install → setup skipped on every subsequent launch.
- **Dev** (local source, no bundled wheels): sentinel is never written → `pypsa-app` is reinstalled from local source on every launch (`uv pip install --reinstall-package pypsa-app`). Deps are left untouched so restarts stay fast.

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

### Rebuilding the pypsa-app wheel (Windows distribution only)

**You do not need this for daily development** — see the Development Workflow section for the faster manual `uv` approach.

Build the wheel when you are ready to produce a new Windows installer. The SvelteKit frontend must be compiled first; `wails build` does **not** do this (the Wails binary only contains the splash screen in `desktop/frontend/`).

```bash
# 1. Build the SvelteKit app
#    Output goes directly to src/pypsa_app/backend/static/app/
cd frontend/app
pnpm run build

# 2. Build the Python wheel
#    Packages static files via MANIFEST.in, output in dist/
cd ../..
uv build
```

The resulting `dist/pypsa_app-X.Y.Z-py3-none-any.whl` is the file to drop into the installer's `wheels/` directory.

---

## Installer

Built with **NSIS** (Wails' recommended Windows installer toolchain). The `.nsi` script lives in `desktop/build/windows/installer/project.nsi`.

The installer bundles:
- `pypsa-desktop.exe` (the Wails binary)
- `uv.exe` (placed at `%PROGRAMFILES%\pypsa-desktop\uv.exe`)
- Pre-built `.whl` files for both Python apps and their dependencies (placed under `%PROGRAMFILES%\pypsa-desktop\wheels\`)

At the end of installation the NSIS script checks for Git and Pixi using `where.exe` and shows a message box listing any that are missing, with install instructions.

**Built locally**: Installer is built manually on a developer Windows machine using NSIS. No GitHub Actions pipeline in v1.

**Code signing**: Required to avoid Windows SmartScreen "unknown publisher" block. Use a code signing certificate for production releases.

### Building the installer

The full installer can be built from **macOS** (recommended) or from Windows.
See `docs/desktop-build-and-distribute.md` → "Windows" for the complete step-by-step.

Short form (macOS with `brew install mingw-w64 makensis`):

```bash
# 1. Build frontend + Python wheels
cd frontend/app && pnpm run build
cd <pypsa-app root>     && uv build
cd <snakedispatch root> && uv build

# 2. Collect win_amd64/cp313 wheels via uv export + pip download
#    (see desktop-build-and-distribute.md Step 3W for the full marker-filter script)

# 3. Download uv.exe
curl -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip \
    -o /tmp/uv-windows.zip && unzip /tmp/uv-windows.zip uv.exe -d desktop/build/windows/

# 4. Build exe + NSIS installer in one command
cd desktop
GOOS=windows GOARCH=amd64 CGO_ENABLED=1 CC=x86_64-w64-mingw32-gcc \
    wails build -platform windows/amd64 -nsis
# Output: desktop/build/bin/pypsa-desktop-setup-v0.1.0-amd64.exe (~250 MB)
```

> **Wheel collection note**: `uv` has no `pip download` subcommand. Use `uv export
> --format requirements-txt` to get a pinned list, filter environment markers for
> win_amd64 (removes `uvloop`, keeps `colorama`/`tzdata`), then use
> `python3 -m pip download --platform win_amd64 --only-binary :all:`.
> The `wheels/` directories are gitignored. Total installer size is ~250 MB.

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

- [x] `desktop/` project: `wails init`, configure Go module
- [x] Minimal splash screen frontend (SvelteKit or plain HTML): status text, progress bar, error view
- [x] WebView navigation: splash → app URL once healthy
- [x] System tray: Show window, Quit
- [x] Basic port conflict detection (log and abort with message if :8765/:8766 are taken)

### Phase 2 — Process management (~3 days)

- [x] `process.go`: spawn subprocess, capture stdout/stderr to rotating log file, detect exit
- [x] Health polling: GET /health on both services, retry with backoff, timeout
- [x] Graceful shutdown: SIGTERM to children, wait up to 5s, then SIGKILL
- [x] Crash recovery: restart a dead sidecar up to 3 times before surfacing error to user
- [x] Pass correct env vars to pypsa-app:
  - `DATABASE_URL=sqlite:///%APPDATA%\pypsa-desktop\data\pypsa-app.db`
  - `DATA_DIR=%APPDATA%\pypsa-desktop\data`
  - `SNAKEDISPATCH_BACKENDS=local=http://localhost:8766`
  - `BASE_URL=http://localhost:8765`

### Phase 3 — First-launch setup (~3 days)

- [x] `prereqs.go`: check Git and Pixi in PATH, return structured results
- [x] `setup.go`: detect venvs, run uv to create and populate them from bundled wheels, stream progress to frontend
- [x] Splash screen shows per-step warm-up progress ("Installing pypsa-app... 47%")
- [x] On error: show actionable message (e.g. "Git not found. Install from git-scm.com and restart.")
- [x] Mark setup complete in a sentinel file so it's skipped on subsequent launches

### Phase 4 — snakedispatch config generation (~1 day)

- [x] Write `snakedispatch.yaml` to `%APPDATA%\pypsa-desktop\config\` on first launch
- [x] Local backend config: `scratch_dir`, `pixi_path` (resolved from PATH), `poll_interval: 5`
- [x] Pass config path to snakedispatch via env var or CLI arg

### Phase 5 — Installer (~2 days)

- [x] `desktop/build/windows/installer/project.nsi`: NSIS script (extends Wails scaffold)
- [x] Bundle exe, uv.exe, wheels directory (built manually, no CI) — script references `../uv.exe` and `../wheels/`
- [x] Detect Git/Pixi absence at end of installation, show message with install instructions
- [x] Uninstaller removes `%PROGRAMFILES%\pypsa-desktop\` only — user data at `%APPDATA%\pypsa-desktop\` preserved
- [x] Output: `pypsa-desktop-setup-v${VERSION}-amd64.exe` — see "Building the installer" section above

### Phase 6 — Polish & release (~2 days)

- [x] Code signing: NSIS hooks pre-wired (commented out in `project.nsi`); see "Code signing" below
- [x] Windows toast notification on fatal crash (`notify_windows.go` via `go-toast`; fires before window is shown)
- [x] "About" systray menu: shows pypsa-app version, snakedispatch version, Python version (`about.go` + `systray_windows.go`)
- [ ] Smoke test on a clean Windows 11 VM — checklist below

### Code signing

To avoid the Windows SmartScreen "Unknown Publisher" block, the Wails binary and installer must be signed with a code signing certificate.

**For internal / close-client distribution (self-signed):**
```powershell
# Generate self-signed cert (run once on the developer machine)
New-SelfSignedCertificate -Type CodeSigning -Subject "CN=pypsa-desktop" `
    -KeyUsage DigitalSignature -FriendlyName "pypsa-desktop" `
    -CertStoreLocation Cert:\CurrentUser\My -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")

# Export to PFX
$cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq "CN=pypsa-desktop" }
Export-PfxCertificate -Cert $cert -FilePath cert.pfx -Password (Read-Host -AsSecureString)

# Sign the exe and installer using signtool (Windows SDK)
signtool sign /fd SHA256 /f cert.pfx /p <password> pypsa-desktop.exe
signtool sign /fd SHA256 /f cert.pfx /p <password> pypsa-desktop-setup-v0.1.0-amd64.exe
```

Self-signed certs still require the recipient to manually trust the cert on first run. For wider distribution, use a CA-issued OV or EV code signing certificate (DigiCert, Sectigo, etc.).

**Wiring it into the build:** Uncomment the `!finalize` / `!uninstfinalize` lines in `project.nsi` and set `CERT_PASSWORD`.

### Smoke test checklist (Windows 11 VM)

Run these on a **clean Windows 11 install** (no Python, no existing pypsa-desktop) before each release.

**Installer**
- [ ] Installer runs without UAC prompt errors
- [ ] SmartScreen warning appears (expected without EV cert); user can bypass via "More info → Run anyway"
- [ ] Install completes without errors; shortcut appears on Desktop and Start Menu
- [ ] Prerequisite warning shown if Git or Pixi is absent

**First launch**
- [ ] Splash screen appears
- [ ] uv downloads Python 3.13 automatically (no Python pre-installed)
- [ ] First-launch setup progress bar advances through both venv installs
- [ ] App navigates to `http://localhost:8767` and the pypsa-app UI loads
- [ ] Runs nav is visible (snakedispatch backend wired up)
- [ ] System tray icon appears with correct tooltip

**System tray**
- [ ] "Show Window" brings window to foreground
- [ ] "About" shows correct pypsa-app, snakedispatch, and Python versions
- [ ] "Quit" stops both sidecars and exits cleanly

**Subsequent launch**
- [ ] Warm-up is skipped (sentinel file present); app starts in < 5 s
- [ ] Previously uploaded networks still visible (SQLite preserved)

**Crash recovery**
- [ ] Kill one sidecar process manually (`taskkill /F /PID <pid>`) — app restarts it
- [ ] Kill the sidecar 3 more times — toast notification appears, error shown in UI

**Uninstaller**
- [ ] Uninstaller removes `C:\Program Files\pypsa-desktop\` completely
- [ ] `%APPDATA%\pypsa-desktop\` is **not** removed (user data preserved)
- [ ] Shortcuts removed from Desktop and Start Menu
- [ ] App no longer appears in "Apps & features"

---

## Decisions

| # | Decision |
|---|---|
| 1 | **Wheel build**: Built from the developer's macOS machine using cross-compilation (`mingw-w64` + `makensis` via Homebrew). No Windows machine required. Development and iteration happen on macOS M4 using manual `uv` commands — no Wails involved. No GitHub Actions CI in v1. |
| 2 | **Version pinning**: `desktop/versions.yaml` pins both `pypsa-app` and `snakedispatch` versions for each installer release. Go code reads this file at build time. |
| 3 | **Local backend in admin**: The bundled snakedispatch appears as **"local (managed)"** — visible but not editable. Users can freely add additional remote backends via the admin panel. |
| 4 | **Authentication**: No auth providers configured for desktop installs (no OAuth clients, `AUTH_PASSWORD_ENABLED` not set). Single shared instance per machine. Acceptable for v1 close-client distribution. |
| 5 | **Dependency bundle**: Ship pre-built wheels (300–500 MB) in the installer. No internet required after install. If bundle size becomes a concern in a future release, switch to first-launch warm-up via PyPI download — the warm-up UI already supports this flow. |
