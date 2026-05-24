package main

import (
	_ "embed"
	"fmt"
	"os/exec"
	"strings"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

//go:embed versions.yaml
var versionsYAML []byte

type pinnedVersions struct {
	PypsaApp      string
	Snakedispatch string
}

// loadPinnedVersions parses the embedded versions.yaml.
// The file is intentionally simple (two "key: value" lines) so we avoid
// pulling in a YAML library just for this.
func loadPinnedVersions() pinnedVersions {
	v := pinnedVersions{PypsaApp: "unknown", Snakedispatch: "unknown"}
	for _, line := range strings.Split(string(versionsYAML), "\n") {
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.Trim(strings.TrimSpace(parts[1]), `"`)
		switch key {
		case "pypsa-app":
			v.PypsaApp = val
		case "snakedispatch":
			v.Snakedispatch = val
		}
	}
	return v
}

// detectPythonVersion runs the Python binary in the pypsa-app venv and returns
// the version string (e.g. "Python 3.13.1"). Returns "unknown" on any error.
func detectPythonVersion(dataDir string) string {
	py := venvScript(dataDir, "pypsa-app", "python")
	out, err := exec.Command(py, "--version").Output()
	if err != nil {
		return "unknown"
	}
	return strings.TrimSpace(string(out))
}

// ShowAbout displays a native dialog with version information.
// Called from the system tray "About" menu item.
func (a *App) ShowAbout() {
	v := loadPinnedVersions()
	py := detectPythonVersion(a.dataDir)
	msg := fmt.Sprintf(
		"pypsa-app:       %s\nsnakedispatch:   %s\nPython:          %s",
		v.PypsaApp, v.Snakedispatch, py,
	)
	_, _ = runtime.MessageDialog(a.ctx, runtime.MessageDialogOptions{
		Type:    runtime.InfoDialog,
		Title:   "About pypsa-desktop",
		Message: msg,
	})
}
