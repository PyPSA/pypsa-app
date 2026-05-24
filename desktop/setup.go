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
		if s.venvReady(t.name) {
			progress(t.hi, fmt.Sprintf("%s already installed.", t.name))
			continue
		}

		progress(t.lo, fmt.Sprintf("Creating %s environment…", t.name))
		if err := s.createVenv(t.name, logPath); err != nil {
			return fmt.Errorf("Creating %s environment: %w", t.name, err)
		}

		progress(t.lo+span/4, fmt.Sprintf("Installing %s…", t.name))
		if err := s.installPkg(t.name, t.pkg, logPath); err != nil {
			return fmt.Errorf("Installing %s: %w", t.name, err)
		}
	}

	progress(hi, "Setup complete.")
	return os.WriteFile(
		filepath.Join(s.dataDir, "venvs", setupSentinel),
		[]byte("ok"), 0o644,
	)
}

func (s *Setup) createVenv(name, logPath string) error {
	venvPath := filepath.Join(s.dataDir, "venvs", name)
	// uv will auto-download Python 3.13 if not present on the system.
	return s.run(logPath, s.uvBin, "venv", "--python", "3.13", venvPath)
}

func (s *Setup) installPkg(venvName, pkg, logPath string) error {
	venvPath := filepath.Join(s.dataDir, "venvs", venvName)
	args := []string{"pip", "install", "--python", venvPath}

	switch {
	case s.wheelsDir != "":
		// Production: install from bundled wheels, no internet needed.
		wheelDir := filepath.Join(s.wheelsDir, venvName)
		args = append(args, "--no-index", "--find-links", wheelDir, pkg)
	case devInstallSpec(venvName) != "":
		// Dev: use auto-detected or env-var-specified local source.
		args = append(args, devInstallSpec(venvName))
	default:
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

// findLocalSrc walks up from cwd looking for a pyproject.toml that names venvName.
// If not found going up, it also scans sibling directories of the first ancestor
// that has any pyproject.toml — this handles packages in sibling repos.
func findLocalSrc(venvName string) string {
	cwd, err := os.Getwd()
	if err != nil {
		return ""
	}
	altName := strings.ReplaceAll(venvName, "-", "_")
	matches := func(data []byte) bool {
		c := string(data)
		return strings.Contains(c, `"`+venvName+`"`) || strings.Contains(c, `"`+altName+`"`)
	}

	// Walk up; track the parent of the first dir that has any pyproject.toml
	// (that's the workspace root — scan its children as siblings).
	var siblingParent string
	dir := cwd
	for range 5 {
		data, err := os.ReadFile(filepath.Join(dir, "pyproject.toml"))
		if err == nil {
			if matches(data) {
				return dir // direct hit
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

	// Scan siblings of the project root.
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
	if runtime.GOOS == "windows" {
		return `C:\Program Files\pypsa-desktop\uv.exe`
	}
	return ""
}

func bundledWheelsDir() string {
	if runtime.GOOS != "windows" {
		return ""
	}
	dir := `C:\Program Files\pypsa-desktop\wheels`
	if _, err := os.Stat(dir); err != nil {
		return ""
	}
	return dir
}
