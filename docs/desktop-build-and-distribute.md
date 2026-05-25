# Desktop Build and Distribute

Quick reference for producing and shipping pypsa-desktop installers.
For architecture decisions and phase history, see `docs/desktop-distribution.md`.

---

## Overview

| Target | Status | Package | Offline install |
|--------|--------|---------|----------------|
| Windows 10/11 x64 | Implemented | NSIS `.exe` installer | Yes — wheels bundled |
| macOS 12+ (arm64 / x64) | Implemented | `.dmg` or `.app` zip | Yes — wheels bundled |
| Linux x64 (Ubuntu 22.04+) | Partial | `.deb` or tarball | No — PyPI on first launch |

All three targets share the same Wails control plane (`desktop/`) and the same two
Python sidecars (pypsa-app on `:8765`, snakedispatch on `:8766`). Data is stored in the
platform config directory:

| Platform | Data directory |
|----------|---------------|
| Windows | `%APPDATA%\pypsa-desktop\` |
| macOS | `~/Library/Application Support/pypsa-desktop/` |
| Linux | `~/.config/pypsa-desktop/` |

---

## Developer prerequisites

**All platforms**

| Tool | Install |
|------|---------|
| Go 1.23+ | https://go.dev/dl/ |
| Wails v2 CLI | `go install github.com/wailsapp/wails/v2/cmd/wails@latest` |
| pnpm | `npm i -g pnpm` |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

**macOS build machine (can build Windows, macOS, and Linux targets)**

```bash
# Xcode command-line tools (codesign, hdiutil, xcrun)
xcode-select --install

# Cross-compiler for Windows/amd64 targets
brew install mingw-w64

# NSIS installer builder (used automatically by wails build -nsis)
brew install makensis

# Optional: nicer DMG layout
brew install create-dmg
```

**Windows build machine only** (alternative to macOS cross-build)

| Tool | Install |
|------|---------|
| NSIS 3.x | `winget install NSIS.NSIS` |
| Windows SDK (signtool) | Visual Studio installer → "Desktop development with C++" |

**Linux build machine only** (Ubuntu 22.04)

```bash
sudo apt install build-essential libwebkit2gtk-4.1-dev libgtk-3-dev
```

---

## Step 1 — Build the SvelteKit frontend (all platforms)

The built static files are packaged into the Python wheel, so this must run first.

```bash
cd frontend/app
pnpm install
pnpm run build
# Output → src/pypsa_app/backend/static/app/
```

---

## Windows

> All steps below can be run from **macOS** (the cross-compile path) or from a
> Windows machine. macOS is the recommended primary build environment.

### Step 2W — Build the Python wheels

```bash
# Run in each repo root (macOS or Windows):
cd <pypsa-app root>    && uv build  # → dist/pypsa_app-X.Y.Z-py3-none-any.whl
cd <snakedispatch root> && uv build  # → dist/snakedispatch-X.Y.Z-py3-none-any.whl
```

### Step 3W — Collect dependency wheels

`uv` does not expose a `pip download` subcommand. Use `uv export` to get a
pinned requirements list, filter environment markers for the win_amd64 target,
then download with `python3 -m pip download`.

```bash
# ── pypsa-app ─────────────────────────────────────────────────────────────────

# 1. Export pinned deps (no hashes, no -e lines)
uv export --format requirements-txt --no-hashes --package pypsa-app \
    | grep -v '^#\|^-e\|^$' > /tmp/pypsa-app-requirements.txt

# 2. Filter markers for win_amd64 (removes uvloop which has no Windows wheel,
#    keeps colorama/tzdata/greenlet which are Windows-only or amd64-conditional)
python3 - << 'EOF'
import re, sys
win_reqs = []
for line in open('/tmp/pypsa-app-requirements.txt'):
    s = line.strip()
    if not s or s.startswith('#'): continue
    if ' ; ' in s:
        spec, marker = s.split(' ; ', 1)
        spec, marker = spec.strip(), marker.strip()
        if 'sys_platform == "win32"' in marker or "sys_platform == 'win32'" in marker:
            win_reqs.append(spec)           # Windows-only: include
        elif "sys_platform != 'win32'" in marker or 'sys_platform != "win32"' in marker:
            pass                            # non-Windows only: skip
        elif 'AMD64' in marker or 'amd64' in marker:
            win_reqs.append(spec)           # AMD64-conditional: include
        else:
            win_reqs.append(spec)           # no OS condition: include
    else:
        win_reqs.append(s)
open('/tmp/pypsa-app-win-requirements.txt', 'w').write('\n'.join(win_reqs) + '\n')
EOF

# 3. Copy the app wheel; download all deps as win_amd64/cp313 wheels
cp <pypsa-app root>/dist/pypsa_app-*.whl desktop/build/windows/wheels/pypsa-app/
python3 -m pip download \
    -r /tmp/pypsa-app-win-requirements.txt \
    --platform win_amd64 --python-version 313 --implementation cp --abi cp313 \
    --only-binary :all: \
    -d desktop/build/windows/wheels/pypsa-app/

# ── snakedispatch ─────────────────────────────────────────────────────────────

# Repeat for snakedispatch (same filtering logic, fewer deps)
cd <snakedispatch root>
uv export --format requirements-txt --no-hashes \
    | grep -v '^#\|^-e\|^$' > /tmp/snakedispatch-requirements.txt
# Apply the same Python marker-filter script (swap filenames), then:
cp <snakedispatch root>/dist/snakedispatch-*.whl desktop/build/windows/wheels/snakedispatch/
python3 -m pip download \
    -r /tmp/snakedispatch-win-requirements.txt \
    --platform win_amd64 --python-version 313 --implementation cp --abi cp313 \
    --only-binary :all: \
    -d desktop/build/windows/wheels/snakedispatch/
```

> **Why `python3 -m pip download` and not `pip download --platform` directly?**
> pip evaluates environment markers against the *host* platform, not the target.
> Exporting the pinned list with `uv export` and filtering markers manually avoids
> pulling `uvloop` (which has no Windows wheel) while correctly including
> `colorama`, `tzdata`, and `greenlet`.

### Step 4W — Get uv.exe

```bash
curl -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip \
    -o /tmp/uv-windows.zip
unzip /tmp/uv-windows.zip uv.exe -d desktop/build/windows/
```

### Step 5W — Cross-compile the Wails binary and build the NSIS installer

With `mingw-w64` and `makensis` installed (see prerequisites), a single command
builds the exe and runs the NSIS installer script automatically:

```bash
cd desktop
GOOS=windows GOARCH=amd64 CGO_ENABLED=1 CC=x86_64-w64-mingw32-gcc \
    wails build -platform windows/amd64 -nsis
# Produces:
#   build/bin/pypsa-desktop.exe
#   build/bin/pypsa-desktop-setup-v0.1.0-amd64.exe  (~250 MB)
#   build/windows/installer/wails_tools.nsh          (auto-generated, gitignored)
```

> **On Windows** (without the cross-compile env vars):
> ```powershell
> cd desktop
> wails build -platform windows/amd64 -nsis
> ```
> If NSIS is not in PATH, `wails build -nsis` will skip the installer step.
> Run makensis manually in that case:
> ```powershell
> cd build\windows\installer
> makensis -DARG_WAILS_AMD64_BINARY=..\..\bin\pypsa-desktop.exe project.nsi
> ```

### Step 7W — Sign (optional)

Without signing, SmartScreen shows an "Unknown Publisher" warning. For close-client
distribution this is acceptable. For wider release use a CA-issued OV/EV certificate.

```powershell
# Sign the exe and installer with signtool
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
    /f cert.pfx /p $env:CERT_PASSWORD `
    desktop\build\bin\pypsa-desktop.exe

signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
    /f cert.pfx /p $env:CERT_PASSWORD `
    desktop\build\bin\pypsa-desktop-setup-v0.1.0-amd64.exe
```

See `docs/desktop-distribution.md` → "Code signing" for how to generate a self-signed
cert for internal distribution.

The NSIS signing hooks are pre-wired in `project.nsi` (commented out) — uncomment the
`!finalize` / `!uninstfinalize` lines to sign automatically during `makensis`.

### Step 8W — Distribute

Ship the single file:

```
pypsa-desktop-setup-v0.1.0-amd64.exe   (~300–500 MB)
```

No companion files needed. The installer is self-contained.

| Path | Contents | Uninstall behaviour |
|------|----------|---------------------|
| `C:\Program Files\pypsa-desktop\` | Wails exe, uv.exe, wheels | Removed |
| `%APPDATA%\pypsa-desktop\` | SQLite DB, venvs, logs, run data | **Preserved** |

### Releasing a new version

1. Bump all three version fields in lockstep (see [Versioning](#versioning)).
2. Rebuild the wheels for both apps (steps 2W–3W).
3. Rebuild the Wails binary (step 5W).
4. Rebuild the installer (step 6W).
5. Ship the new `.exe`. Users run it over the existing install — no data migration needed.

---

## macOS

> **Status**: Implemented and tested on M4 (arm64) and Intel x86_64. Two separate
> DMGs are produced — one per architecture — each containing a **universal binary**
> (arm64 + x86_64) with architecture-specific uv and wheels bundled inside.
> First-launch setup is fully offline. WKWebView is built into macOS 12+; no extra
> runtime dependencies.
>
> **Python version**: arm64 bundle uses Python 3.13; x86_64 bundle also uses Python
> 3.13 (Bottleneck 1.6.0 is built from source as a universal2 wheel). The binary
> auto-detects the correct Python version from the wheel filenames at runtime via
> `inferPythonVersion()` in `setup.go`.
>
> **Minimum macOS**: arm64 — macOS 11+; x86_64 — macOS 14+ (numpy/scipy require it).

### Step 2M — Build the Python wheels

```bash
cd <pypsa-app root>   && uv build   # → dist/pypsa_app-X.Y.Z-py3-none-any.whl
cd <snakedispatch root> && uv build  # → dist/snakedispatch-X.Y.Z-py3-none-any.whl
```

### Step 3M — Collect dependency wheels

`uv pip download` does not exist in uv ≤ 0.9.x. Resolve via native install then
`pip download` the pinned set cross-platform:

```bash
# ── arm64 (Apple Silicon) ──────────────────────────────────────────────────
uv venv /tmp/pypsa-collect --python 3.13 --seed

# Resolve arm64 deps via native install, then freeze to pin exact versions
uv venv /tmp/resolve --python 3.13 --seed
/tmp/resolve/bin/pip install pypsa-app --find-links <pypsa-app root>/dist -q
/tmp/resolve/bin/pip freeze | grep -v pypsa.app > /tmp/pypsa-deps.txt
/tmp/resolve/bin/pip freeze | grep -v snakedispatch > /tmp/snkd-deps.txt

# Download pinned wheels for arm64
/tmp/pypsa-collect/bin/pip download \
    -r /tmp/pypsa-deps.txt \
    --dest desktop/build/darwin/wheels/pypsa-app \
    --python-version 3.13 --platform macosx_11_0_arm64 --only-binary :all:
cp <pypsa-app root>/dist/pypsa_app-*.whl desktop/build/darwin/wheels/pypsa-app/

/tmp/pypsa-collect/bin/pip download \
    -r /tmp/snkd-deps.txt \
    --dest desktop/build/darwin/wheels/snakedispatch \
    --python-version 3.13 --platform macosx_11_0_arm64 --only-binary :all:
cp <snakedispatch root>/dist/snakedispatch-*.whl desktop/build/darwin/wheels/snakedispatch/

# ── x86_64 (Intel Mac) ────────────────────────────────────────────────────
# Bottleneck 1.6.0 has no PyPI x86_64 macOS wheel for Python 3.13.
# Build it from source using the system Python 3.13 universal2 binary via Rosetta:
arch -x86_64 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 \
    -m venv /tmp/pypsa-x86-build
arch -x86_64 /tmp/pypsa-x86-build/bin/pip wheel "Bottleneck==1.6.0" \
    --wheel-dir /tmp/bottleneck-x86-wheel -q
# → bottleneck-1.6.0-cp313-cp313-macosx_10_13_universal2.whl

# Resolve for x86_64 (Bottleneck as an extra find-links source)
/tmp/pypsa-collect/bin/pip download \
    -r /tmp/pypsa-deps.txt \
    --find-links /tmp/bottleneck-x86-wheel \
    --dest desktop/build/darwin-x86/wheels/pypsa-app \
    --python-version 3.13 --platform macosx_14_0_x86_64 --only-binary :all:
cp <pypsa-app root>/dist/pypsa_app-*.whl desktop/build/darwin-x86/wheels/pypsa-app/
cp /tmp/bottleneck-x86-wheel/bottleneck-*.whl desktop/build/darwin-x86/wheels/pypsa-app/

/tmp/pypsa-collect/bin/pip download \
    -r /tmp/snkd-deps.txt \
    --dest desktop/build/darwin-x86/wheels/snakedispatch \
    --python-version 3.13 --platform macosx_14_0_x86_64 --only-binary :all:
cp <snakedispatch root>/dist/snakedispatch-*.whl desktop/build/darwin-x86/wheels/snakedispatch/
```

Collected wheels are gitignored (`*.whl`). See `desktop/build/darwin/.gitignore`.

### Step 4M — Get uv binaries

```bash
# arm64 (from the build machine)
cp $(which uv) desktop/build/darwin/uv

# x86_64 (download from GitHub releases — match current uv version)
UV_VERSION=$(uv --version | awk '{print $2}')
curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-apple-darwin.tar.gz" \
    | tar -xzO uv-x86_64-apple-darwin/uv > desktop/build/darwin-x86/uv
chmod +x desktop/build/darwin-x86/uv
```

### Step 5M — Build the universal Wails binary

A single universal binary (arm64 + x86_64) is shared between both DMGs:

```bash
cd desktop
wails build -platform darwin/universal
# Output: build/bin/pypsa-desktop.app  (universal binary ~20 MB, self-signed)
```

### Step 6M — Assemble bundles

```bash
# arm64 bundle — uses the .app produced by wails build directly
ARM64_APP=desktop/build/bin/pypsa-desktop.app/Contents/MacOS
cp desktop/build/darwin/uv     "$ARM64_APP/uv"
cp -r desktop/build/darwin/wheels "$ARM64_APP/wheels"
chmod +x "$ARM64_APP/uv"

# x86_64 bundle — copy the app then inject x86_64 assets
X86_APP=desktop/build/bin/pypsa-desktop-x86_64.app
cp -r desktop/build/bin/pypsa-desktop.app "$X86_APP"
X86_MACOS="$X86_APP/Contents/MacOS"
cp desktop/build/darwin-x86/uv        "$X86_MACOS/uv"
cp -r desktop/build/darwin-x86/wheels "$X86_MACOS/wheels"
chmod +x "$X86_MACOS/uv"
```

`setup.go`'s `inferPythonVersion()` reads the `cpXYZ` tag from wheel filenames to
pick the right Python version automatically — no separate config file needed.

After injection, `bundledWheelsDir()` finds the wheels at `<Contents/MacOS>/wheels`
and first-launch setup runs fully offline on both architectures.

### Step 7M — Package as DMGs

```bash
# arm64 DMG
create-dmg \
    --volname "pypsa-desktop" \
    --window-pos 200 120 --window-size 600 400 \
    --icon-size 100 \
    --icon "pypsa-desktop.app" 175 190 \
    --hide-extension "pypsa-desktop.app" \
    --app-drop-link 425 190 \
    --no-internet-enable \
    "desktop/build/bin/pypsa-desktop-v0.1.0-arm64.dmg" \
    "desktop/build/bin/pypsa-desktop.app"
# Output: ~260 MB (universal binary + arm64 wheels)

# x86_64 DMG
create-dmg \
    --volname "pypsa-desktop" \
    --window-pos 200 120 --window-size 600 400 \
    --icon-size 100 \
    --icon "pypsa-desktop.app" 175 190 \
    --hide-extension "pypsa-desktop.app" \
    --app-drop-link 425 190 \
    --no-internet-enable \
    "desktop/build/bin/pypsa-desktop-v0.1.0-x86_64.dmg" \
    "desktop/build/bin/pypsa-desktop-x86_64.app"
# Output: ~380 MB (universal binary + x86_64 wheels, polars-runtime-32 is larger)
```

### Step 7M (alt) — Ship a zipped .app

```bash
cd desktop/build/bin
zip -r pypsa-desktop-0.1.0-arm64.zip pypsa-desktop.app
zip -r pypsa-desktop-0.1.0-x86_64.zip pypsa-desktop-x86_64.app
```

### Step 8M — Sign and notarize (optional)

Without signing, Gatekeeper shows "cannot be opened because it is from an unidentified
developer." For close clients this is workable — instruct users to right-click → Open
on first launch, or run:

```bash
xattr -dr com.apple.quarantine /Applications/pypsa-desktop.app
```

For wider distribution, sign and notarize with an Apple Developer ID ($99/year):

**1. Create an entitlements file** (`desktop/build/darwin/entitlements.plist`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Required for WKWebView JIT compilation -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <!-- Required for unsigned bundled binaries (uv, python) -->
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <!-- Required for WebView to make network requests -->
    <key>com.apple.security.network.client</key>
    <true/>
</dict>
</plist>
```

**2. Sign the app bundle** (sign bundled binaries first, then the outer bundle):

```bash
codesign --sign "Developer ID Application: Your Name (TEAMID)" \
    desktop/build/bin/pypsa-desktop.app/Contents/MacOS/uv

codesign --deep --sign "Developer ID Application: Your Name (TEAMID)" \
    --options runtime \
    --entitlements desktop/build/darwin/entitlements.plist \
    desktop/build/bin/pypsa-desktop.app
```

**3. Sign the DMG:**

```bash
codesign --sign "Developer ID Application: Your Name (TEAMID)" \
    desktop/build/bin/pypsa-desktop-v0.1.0-arm64.dmg
```

**4. Submit for notarization and staple:**

```bash
xcrun notarytool submit desktop/build/bin/pypsa-desktop-v0.1.0-arm64.dmg \
    --apple-id your@apple.id \
    --password "$APP_SPECIFIC_PASSWORD" \
    --team-id TEAMID \
    --wait

xcrun stapler staple desktop/build/bin/pypsa-desktop-v0.1.0-arm64.dmg
```

> **App-specific password**: generate at appleid.apple.com → Sign-In and Security →
> App-Specific Passwords.

### Step 9M — Distribute

Ship the DMG matching the recipient's Mac:
- `pypsa-desktop-v0.1.0-arm64.dmg` — Apple Silicon (M1/M2/M3/M4) — requires macOS 11+
- `pypsa-desktop-v0.1.0-x86_64.dmg` — Intel Mac — requires **macOS 14** (Sonoma)

No companion tools needed. uv and all Python packages are bundled. Python 3.13 is
downloaded by uv on first launch (~30 s), then packages install from bundled wheels
(~2–3 min).

### macOS-specific behaviour

| Feature | macOS |
|---------|-------|
| System tray | Not implemented — closing the window quits the app |
| About dialog | Implemented — tray menu → About (same as Windows) |
| Crash toast | Not implemented — error shown in app window |
| Offline install | Yes — uv + arch-specific wheels inside `Contents/MacOS/` |
| Minimum macOS | arm64: 11+; x86_64: 14+ (numpy/scipy require it) |
| Gatekeeper | Right-click → Open on first launch, or `xattr -dr com.apple.quarantine <app>` |
| Sidecar shutdown | SIGTERM → SIGKILL after 5 s |

---

## Linux

> **Status**: The Wails binary builds and runs on Linux. First-launch setup downloads
> Python packages from PyPI (internet required). Offline wheel bundling is not yet
> implemented — see [Future: offline bundle](#future-offline-bundle-on-linux).

### Runtime dependencies (end-user machine)

```bash
# Ubuntu 22.04 / Debian 12+
sudo apt install libwebkit2gtk-4.1-0 libgtk-3-0

# Ubuntu 20.04 / Debian 11
sudo apt install libwebkit2gtk-4.0-37 libgtk-3-0
```

`uv` must be in PATH for the first-launch venv setup:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: pip install uv --user
```

### Step 2L — Build the Python wheels

```bash
cd <pypsa-app root>  && uv build   # → dist/pypsa_app-X.Y.Z-py3-none-any.whl
cd <snakedispatch root> && uv build # → dist/snakedispatch-X.Y.Z-py3-none-any.whl
```

### Step 3L — Build the Wails binary

```bash
cd desktop
wails build --target linux/amd64
# Output: build/bin/pypsa-desktop  (ELF binary, ~10–20 MB)
```

### Step 4L — Package as .deb (Ubuntu/Debian)

Create the package tree:

```
pypsa-desktop_0.1.0_amd64/
├── DEBIAN/
│   └── control
└── usr/
    ├── bin/
    │   └── pypsa-desktop           ← symlink to ../lib/pypsa-desktop/pypsa-desktop
    └── lib/
        └── pypsa-desktop/
            └── pypsa-desktop       ← Wails binary
```

`DEBIAN/control`:

```
Package: pypsa-desktop
Version: 0.1.0
Architecture: amd64
Maintainer: mikoding <mikoding9@gmail.com>
Depends: libwebkit2gtk-4.1-0 | libwebkit2gtk-4.0-37, libgtk-3-0, uv
Description: pypsa-desktop
 Network planning and dispatch optimisation desktop application.
 First launch requires internet access to install Python dependencies.
```

Build and install:

```bash
# Create the symlink
mkdir -p pypsa-desktop_0.1.0_amd64/usr/bin
ln -s ../lib/pypsa-desktop/pypsa-desktop \
    pypsa-desktop_0.1.0_amd64/usr/bin/pypsa-desktop

# Copy the binary
mkdir -p pypsa-desktop_0.1.0_amd64/usr/lib/pypsa-desktop
cp desktop/build/bin/pypsa-desktop \
    pypsa-desktop_0.1.0_amd64/usr/lib/pypsa-desktop/

dpkg-deb --build pypsa-desktop_0.1.0_amd64
# → pypsa-desktop_0.1.0_amd64.deb (~15 MB without bundled wheels)
```

Install on the user's machine:

```bash
sudo apt install ./pypsa-desktop_0.1.0_amd64.deb
pypsa-desktop   # first launch downloads Python deps (~2–3 min)
```

### Step 4L (alt) — Package as tarball (distro-agnostic)

```bash
mkdir pypsa-desktop-0.1.0-linux-x64
cp desktop/build/bin/pypsa-desktop pypsa-desktop-0.1.0-linux-x64/
tar czf pypsa-desktop-0.1.0-linux-x64.tar.gz pypsa-desktop-0.1.0-linux-x64/
```

Include a README instructing users to install the runtime deps listed above.

### Platform feature comparison

| Feature | Linux | macOS | Windows |
|---------|-------|-------|---------|
| System tray | No — closing quits | No — closing quits | Yes — hides to tray |
| About dialog | No | Yes — tray menu | Yes — tray menu |
| Crash notification | No — in-app error | No — in-app error | Windows toast |
| Runtime deps | libwebkit2gtk, libgtk | None (WKWebView built-in) | None (EdgeWebView2 built-in) |
| Offline install | Not yet | Yes (bundled uv + wheels) | Yes (bundled wheels) |
| Data directory | `~/.config/pypsa-desktop/` | `~/Library/Application Support/pypsa-desktop/` | `%APPDATA%\pypsa-desktop\` |
| Sidecar shutdown | SIGTERM → SIGKILL | SIGTERM → SIGKILL | CTRL_BREAK → Kill |
| Package format | `.deb` or tarball | `.dmg` or `.app` zip | NSIS `.exe` installer |

### Future: offline bundle on Linux

To avoid the first-launch PyPI download, two code changes and one packaging change are
needed:

1. **`desktop/setup.go`** — extend `bundledUVPath()` and `bundledWheelsDir()`:
   ```go
   case "linux":
       return "/usr/lib/pypsa-desktop/uv"          // bundledUVPath
   case "linux":
       return "/usr/lib/pypsa-desktop/wheels"      // bundledWheelsDir
   ```

2. **Wheel collection** — download Linux wheels alongside the binary:
   ```bash
   uv pip download pypsa-app \
       --find-links dist/ \
       --output-dir desktop/build/linux/wheels/pypsa-app \
       --python-version 3.13 --platform manylinux_2_17_x86_64 --only-binary :all:
   ```

3. **`.deb` package** — add bundled uv and wheels under `usr/lib/pypsa-desktop/` and
   remove the `uv` entry from `Depends:`.

---

## Versioning

Bump these three files in lockstep for every release:

| File | Field |
|------|-------|
| `desktop/versions.yaml` | `pypsa-app` and `snakedispatch` |
| `desktop/wails.json` | `info.productVersion` |
| `desktop/build/windows/installer/project.nsi` | `!define INFO_PRODUCTVERSION` |

The Windows installer output filename picks up the version automatically:
`pypsa-desktop-setup-v${INFO_PRODUCTVERSION}-${ARCH}.exe`.
Use the same version string in DMG and tarball filenames on macOS/Linux for consistency.

---

## Smoke test checklist

See `docs/desktop-distribution.md` → "Smoke test checklist (Windows 11 VM)" for the
full pre-release checklist covering installer, first launch, tray, crash recovery, and
uninstaller verification.
