# macOS Intel (x86_64) Build — Obstacles and Solutions

Build context: M4 (arm64) build machine, targeting Intel Mac coworker on macOS 14.
Date: 2026-05-24.

---

## 1. `uv pip download` does not exist

**Symptom**

```
$ uv pip download pypsa-app --dest wheels/ --platform macosx_14_0_x86_64
error: unrecognized subcommand 'download'
```

**Cause**

`uv pip download` was not implemented in uv ≤ 0.9.x. The subcommand exists in
newer uv releases, but the version in use (0.9.30) only supports `uv pip install`,
`uv pip compile`, etc.

**Solution**

Create a seeded venv to get a vanilla `pip`, then use `pip download` directly:

```bash
uv venv /tmp/pypsa-collect --python 3.13 --seed
/tmp/pypsa-collect/bin/pip download pypsa-app \
    --dest wheels/pypsa-app \
    --python-version 3.13 --platform macosx_14_0_x86_64 --only-binary :all:
```

---

## 2. pip resolver fails on dev-version wheels with multiple versions in `--find-links`

**Symptom**

```
ERROR: Cannot install pypsa-app because these package versions have conflicting dependencies.
ERROR: ResolutionImpossible
```

**Cause**

The local `dist/` directory contained multiple dev-build wheels of `pypsa-app`
(e.g. `dev108`, `dev112`, `dev115`). When passed as `--find-links dist/`, pip's
resolver tried to reconcile all of them as candidates, hit a constraint conflict, and
gave up.

**Solution**

Stage only the latest wheel in a clean temporary directory before calling
`pip download`:

```bash
mkdir -p /tmp/find-links/pypsa-app
cp dist/pypsa_app-<latest>.whl /tmp/find-links/pypsa-app/
pip download pypsa-app --find-links /tmp/find-links/pypsa-app ...
```

---

## 3. pip resolution still too complex for direct cross-platform download

**Symptom**

Even with a single wheel in `--find-links`, `pip download pypsa-app` with
`--platform macosx_14_0_x86_64` produced:

```
Pip cannot resolve the current dependencies as the dependency graph is too complex
for pip to solve efficiently.
```

**Cause**

`pip download` with `--platform` + a local dev wheel involves resolving transitive
dependencies entirely offline/hypothetically. The pip resolver struggled with the
depth of the pypsa-app dependency tree (86 packages) combined with the cross-platform
constraint.

**Solution**

Split the process into two steps:

1. **Resolve natively** (arm64, same machine) — install into a temp venv and freeze:

   ```bash
   uv venv /tmp/resolve --python 3.13 --seed
   /tmp/resolve/bin/pip install pypsa-app --find-links /tmp/find-links/pypsa-app -q
   /tmp/resolve/bin/pip freeze | grep -v pypsa.app > /tmp/pypsa-deps.txt
   ```

2. **Download cross-platform** using the pinned requirements (no resolver work needed):

   ```bash
   pip download -r /tmp/pypsa-deps.txt \
       --dest wheels/pypsa-app \
       --python-version 3.13 --platform macosx_14_0_x86_64 --only-binary :all:
   ```

---

## 4. Bottleneck 1.6.0 has no macOS x86_64 wheel for Python 3.13

**Symptom**

```
ERROR: Could not find a version that satisfies the requirement Bottleneck==1.6.0
ERROR: No matching distribution found for Bottleneck==1.6.0
```

Tested across every macOS x86_64 platform tag (`macosx_10_13_x86_64` through
`macosx_14_0_x86_64`) — all returned the same error.

**Cause**

Bottleneck 1.6.0 was published to PyPI with only Linux and macOS **arm64** wheels.
No macOS x86_64 wheel exists for Python 3.13 on PyPI. (Older Bottleneck versions
up to 1.3.8 had macOS x86_64 wheels but only up to Python 3.12.)

Bottleneck is a hard dependency of `linopy`, which is a hard dependency of `pypsa`.
There is no way to install pypsa-app without it.

**Solution**

Build Bottleneck from source using the **Rosetta 2** translation layer and the
system Python 3.13 **universal2** binary (installed from python.org):

```bash
# Verify the system Python is universal2 (works on both arm64 and x86_64)
file /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
# → Mach-O universal binary with 2 architectures: [x86_64] [arm64]

# Create an x86_64 venv by forcing x86_64 mode via Rosetta
arch -x86_64 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 \
    -m venv /tmp/pypsa-x86-build

# Build Bottleneck as a wheel (compiles C extension targeting x86_64)
arch -x86_64 /tmp/pypsa-x86-build/bin/pip wheel "Bottleneck==1.6.0" \
    --wheel-dir /tmp/bottleneck-x86-wheel -q
# → bottleneck-1.6.0-cp313-cp313-macosx_10_13_universal2.whl
```

The resulting wheel is tagged `universal2` (contains both architectures), which is
compatible with both Intel and Apple Silicon Macs. It is then provided as an extra
`--find-links` source when calling `pip download`:

```bash
pip download -r /tmp/pypsa-deps.txt \
    --find-links /tmp/bottleneck-x86-wheel \
    --dest wheels/pypsa-app \
    --python-version 3.13 --platform macosx_14_0_x86_64 --only-binary :all:
cp /tmp/bottleneck-x86-wheel/bottleneck-*.whl wheels/pypsa-app/
```

**Prerequisites**: Rosetta 2 must be installed (`softwareupdate --install-rosetta`).
The python.org Python installer (not Homebrew) provides a universal2 binary.

---

## 5. pypsa-app requires Python ≥ 3.13; Bottleneck ≥ 1.6.0 only has x86_64 Python ≤ 3.12

**Symptom**

Attempting to use Python 3.12 as a workaround for Bottleneck:

```
ERROR: Package 'pypsa-app' requires a different Python: 3.12.10 not in '>=3.13'
```

**Cause**

`pypsa-app/pyproject.toml` has `requires-python = ">=3.13"`. Downgrading to Python
3.12 is not an option without also dropping that constraint.

This is what drove the Rosetta build approach in obstacle 4 — there is no clean way to
get Bottleneck for Python 3.13 + macOS x86_64 without building from source.

---

## 6. `netcdf4`, `numpy`, `scipy` require macOS 13–14 for x86_64

**Symptom**

`pip download netcdf4 --platform macosx_11_0_x86_64 --only-binary :all:` returned
no matches.

**Cause**

Recent releases of these scientific packages stopped shipping macOS x86_64 wheels for
older OS versions. The minimum macOS for x86_64 wheels:

| Package | Minimum macOS (x86_64) |
|---------|------------------------|
| netcdf4 | 13.0 |
| numpy   | 14.0 |
| scipy   | 14.0 |
| pyproj  | 13.0 |

Specifying `--platform macosx_14_0_x86_64` causes pip to accept wheels built for any
macOS ≥ 10.x targeting x86_64 (backward-compatible), so all packages resolve.

**Impact on end users**

Intel Mac coworkers need **macOS 14 (Sonoma)** to run the x86_64 bundle. Sonoma
supports Intel Macs from 2018 onwards.

---

## 7. Wails build cross-compilation flag is `-platform`, not `--target`

**Symptom**

```
$ wails build --target darwin/universal
ERROR: flag provided but not defined: -target
```

**Cause**

Wails v2's CLI uses single-dash long flags. The flag is `-platform`, not `--target`.

**Solution**

```bash
wails build -platform darwin/universal
```

This produces a universal binary (arm64 + x86_64) in a single `.app` bundle. The
same universal binary is used in both the arm64 and x86_64 DMGs; only the bundled
`uv` binary and `wheels/` directory differ.

---

## 8. `create-dmg` AppleScript error leaves writable intermediate DMG

**Symptom**

```
execution error: Finder got an error: Can't set item "pypsa-desktop.app" of
disk "dmg.xxxxxx" to {175, 190}. (-10006)
```

The final compressed `.dmg` was never produced; only the intermediate
`rw.xxxxx.pypsa-desktop.dmg` file remained.

**Cause**

`create-dmg` uses AppleScript to position icons in the Finder window of a writable
DMG before compressing it. On some macOS configurations (e.g. when Finder is not
available to the shell process) this Finder IPC call fails. The tool exits after the
error, skipping the `hdiutil convert` step.

**Solution**

Skip `create-dmg` and convert the writable intermediate DMG directly:

```bash
hdiutil convert rw.xxxxx.pypsa-desktop.dmg \
    -format UDZO \
    -o pypsa-desktop-v0.1.0-x86_64.dmg \
    -ov
```

The resulting DMG lacks the Finder background/icon layout but is functionally
identical. For cosmetic DMGs with drag-to-Applications layout, the `create-dmg`
call generally works when run interactively (not inside a headless CI environment).

---

## Summary

| Obstacle | Root cause | Solution |
|----------|-----------|----------|
| `uv pip download` missing | uv ≤ 0.9.x has no download subcommand | Use `uv venv --seed` to get pip, then `pip download` |
| Multiple dev wheels confuse resolver | Old builds in `dist/` | Stage only latest wheel in clean temp dir |
| Resolver too complex for cross-platform | Pip can't resolve deep graph cross-platform | Resolve natively first, freeze, then `pip download -r requirements.txt` |
| Bottleneck has no x86_64 Python 3.13 wheel | PyPI gap — arm64-only for 1.6.x | Build from source via Rosetta (`arch -x86_64`) |
| pypsa-app requires Python ≥ 3.13 | Package constraint | Drives the Rosetta approach; Python 3.12 is not an option |
| netcdf4/numpy/scipy require macOS 14 | New wheel builds target newer SDKs | Use `--platform macosx_14_0_x86_64`; require macOS 14 on Intel |
| Wrong Wails flag | `-platform` not `--target` | `wails build -platform darwin/universal` |
| `create-dmg` AppleScript error | Headless Finder IPC failure | `hdiutil convert rw.xxx.dmg -format UDZO -o final.dmg` |
