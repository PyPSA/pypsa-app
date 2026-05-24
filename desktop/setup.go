package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

const setupSentinel = "setup_complete"

// Setup handles first-launch uv venv creation and package installation.
type Setup struct {
	dataDir   string
	wheelsDir string // empty → install from PyPI (dev / no installer)
	uvBin     string
}

func NewSetup(dataDir string) *Setup {
	return &Setup{
		dataDir:   dataDir,
		wheelsDir: bundledWheelsDir(),
		uvBin:     findUV(),
	}
}

// IsComplete returns true when the sentinel file written at the end of Run() exists.
func (s *Setup) IsComplete() bool {
	_, err := os.Stat(filepath.Join(s.dataDir, "venvs", setupSentinel))
	return err == nil
}

// venvReady returns true when uvicorn exists in the venv.
// Both pypsa-app and snakedispatch install uvicorn as a dependency, making it
// a reliable proxy for "the package install completed successfully".
func (s *Setup) venvReady(name string) bool {
	_, err := os.Stat(venvScript(s.dataDir, name, "uvicorn"))
	return err == nil
}

// Run creates both venvs and installs packages.
// pct is reported in [lo, hi]; output is appended to <dataDir>/logs/setup.log.
// Already-installed venvs are skipped so retries don't redo completed work.
func (s *Setup) Run(lo, hi int, progress func(pct int, msg string)) error {
	logPath := filepath.Join(s.dataDir, "logs", "setup.log")
	span := hi - lo

	type venvTask struct {
		name, pkg string
		lo, hi    int
	}
	tasks := []venvTask{
		{"pypsa-app", "pypsa-app", lo, lo + span/2},
		{"snakedispatch", "snakedispatch", lo + span/2, hi},
	}

	for _, t := range tasks {
		isLocalDev := s.wheelsDir == "" && devInstallSpec(t.name) != ""

		if s.venvReady(t.name) {
			if !isLocalDev {
				progress(t.hi, fmt.Sprintf("%s already installed.", t.name))
				continue
			}
			// Local dev: venv exists but reinstall to pick up source changes.
		} else {
			progress(t.lo, fmt.Sprintf("Creating %s environment…", t.name))
			if err := s.createVenv(t.name, logPath); err != nil {
				return fmt.Errorf("Creating %s environment: %w", t.name, err)
			}
		}

		progress(t.lo+span/4, fmt.Sprintf("Installing %s…", t.name))
		if err := s.installPkg(t.name, t.pkg, logPath); err != nil {
			return fmt.Errorf("Installing %s: %w", t.name, err)
		}
	}

	progress(hi, "Setup complete.")
	// In production (bundled wheels) write the sentinel so setup is skipped on next launch.
	// In dev mode skip it so local source changes are always picked up on restart.
	if s.wheelsDir == "" {
		return nil
	}
	return os.WriteFile(
		filepath.Join(s.dataDir, "venvs", setupSentinel),
		[]byte("ok"), 0o644,
	)
}

func (s *Setup) createVenv(name, logPath string) error {
	venvPath := filepath.Join(s.dataDir, "venvs", name)
	return s.run(logPath, s.uvBin, "venv", "--python", s.pythonVersion(), venvPath)
}

// pythonVersion returns the CPython version to use for venv creation.
// In bundled mode, the version is inferred from the wheel filenames so that
// arm64 bundles (Python 3.13 wheels) and x86_64 bundles (Python 3.12 wheels)
// each get the correct interpreter without a code change per build.
// Falls back to "3.13" for dev/online mode.
func (s *Setup) pythonVersion() string {
	if s.wheelsDir != "" {
		if v := inferPythonVersion(s.wheelsDir); v != "" {
			return v
		}
	}
	return "3.13"
}

// inferPythonVersion scans wheel filenames for a cpXYZ-cpXYZ tag (not abi3,
// not py3-none) and returns the matching Python version string (e.g. "3.12").
func inferPythonVersion(wheelsDir string) string {
	for _, pkg := range []string{"pypsa-app", "snakedispatch"} {
		entries, _ := os.ReadDir(filepath.Join(wheelsDir, pkg))
		for _, e := range entries {
			parts := strings.Split(strings.TrimSuffix(e.Name(), ".whl"), "-")
			if len(parts) < 5 {
				continue
			}
			pyTag, abiTag := parts[2], parts[3]
			if abiTag == "abi3" || abiTag == "none" {
				continue // skip stable-ABI and pure-python wheels
			}
			if strings.HasPrefix(pyTag, "cp") && len(pyTag) == 5 {
				return string(pyTag[2]) + "." + pyTag[3:]
			}
		}
	}
	return ""
}

func (s *Setup) installPkg(venvName, pkg, logPath string) error {
	venvPath := filepath.Join(s.dataDir, "venvs", venvName)
	args := []string{"pip", "install", "--python", venvPath}

	switch {
	case s.wheelsDir != "":
		// Production: install from bundled wheels, no internet needed.
		wheelDir := filepath.Join(s.wheelsDir, venvName)
		_ = appendLogLine(logPath, "installing "+pkg+" from bundled wheels: "+wheelDir)
		args = append(args, "--no-index", "--find-links", wheelDir, pkg)
	case devInstallSpec(venvName) != "":
		// Dev: reinstall only this package from local source; leave deps alone.
		src := devInstallSpec(venvName)
		_ = appendLogLine(logPath, "installing "+pkg+" from local source: "+src)
		args = append(args, "--reinstall-package", pkg, src)
	default:
		_ = appendLogLine(logPath, "installing "+pkg+" from package index")
		args = append(args, pkg)
	}

	return s.run(logPath, s.uvBin, args...)
}

// devInstallSpec returns the install spec for a package in dev mode (no bundled wheels).
// Priority: PYPSA_DESKTOP_SRC_<NAME> env var → auto-detect local source → empty (PyPI).
func devInstallSpec(venvName string) string {
	key := "PYPSA_DESKTOP_SRC_" + strings.ToUpper(strings.ReplaceAll(venvName, "-", "_"))
	if src := os.Getenv(key); src != "" {
		return src
	}
	return findLocalSrc(venvName)
}

// findLocalSrc walks up from cwd (and from the executable's directory as a
// fallback) looking for a pyproject.toml that names venvName. The exe-path
// fallback is needed when running a macOS app bundle, where os.Getwd() is
// $HOME rather than the project directory.
func findLocalSrc(venvName string) string {
	altName := strings.ReplaceAll(venvName, "-", "_")
	matches := func(data []byte) bool {
		c := string(data)
		return strings.Contains(c, `"`+venvName+`"`) || strings.Contains(c, `"`+altName+`"`)
	}

	if cwd, err := os.Getwd(); err == nil {
		if src := walkUpSrc(cwd, matches, 6); src != "" {
			return src
		}
	}
	// Fallback for app bundles: walk up from the executable.
	// e.g. build/bin/pypsa-desktop.app/Contents/MacOS/pypsa-desktop → 7 levels up → project root.
	if exe, err := os.Executable(); err == nil {
		if src := walkUpSrc(filepath.Dir(exe), matches, 9); src != "" {
			return src
		}
	}
	return ""
}

// walkUpSrc walks up at most maxLevels from startDir looking for a
// pyproject.toml that matches. Also scans sibling dirs of the first ancestor
// that has any pyproject.toml (handles packages in sibling repos).
func walkUpSrc(startDir string, matches func([]byte) bool, maxLevels int) string {
	var siblingParent string
	dir := startDir
	for range maxLevels {
		data, err := os.ReadFile(filepath.Join(dir, "pyproject.toml"))
		if err == nil {
			if matches(data) {
				return dir
			}
			if siblingParent == "" {
				siblingParent = filepath.Dir(dir)
			}
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	if siblingParent == "" {
		return ""
	}
	entries, _ := os.ReadDir(siblingParent)
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		candidate := filepath.Join(siblingParent, e.Name())
		data, err := os.ReadFile(filepath.Join(candidate, "pyproject.toml"))
		if err == nil && matches(data) {
			return candidate
		}
	}
	return ""
}

// run executes a command, appending its stdout+stderr to logPath.
func (s *Setup) run(logPath, name string, args ...string) error {
	f, err := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()

	cmd := exec.Command(name, args...)
	cmd.Stdout = f
	cmd.Stderr = f
	return cmd.Run()
}

func appendLogLine(logPath, line string) error {
	f, err := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()

	_, err = fmt.Fprintln(f, line)
	return err
}

func findUV() string {
	if p := bundledUVPath(); p != "" {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	if p, err := exec.LookPath("uv"); err == nil {
		return p
	}
	return "uv"
}

func bundledUVPath() string {
	switch runtime.GOOS {
	case "windows":
		return `C:\Program Files\pypsa-desktop\uv.exe`
	case "darwin":
		exe, err := os.Executable()
		if err != nil {
			return ""
		}
		return filepath.Join(filepath.Dir(exe), "uv")
	default:
		return ""
	}
}

func bundledWheelsDir() string {
	var dir string
	switch runtime.GOOS {
	case "windows":
		dir = `C:\Program Files\pypsa-desktop\wheels`
	case "darwin":
		exe, err := os.Executable()
		if err != nil {
			return ""
		}
		dir = filepath.Join(filepath.Dir(exe), "wheels")
	default:
		return ""
	}
	if _, err := os.Stat(dir); err != nil {
		return ""
	}
	return dir
}
