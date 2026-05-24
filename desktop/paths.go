package main

import (
	"os"
	"path/filepath"
	"runtime"
)

// appDataDir returns the root data directory for pypsa-desktop.
//   - Windows: %APPDATA%\pypsa-desktop
//   - macOS:   ~/Library/Application Support/pypsa-desktop
func appDataDir() string {
	base, err := os.UserConfigDir()
	if err != nil {
		base = os.TempDir()
	}
	return filepath.Join(base, "pypsa-desktop")
}

// venvScript returns the path to a console_scripts entry point inside a uv-managed venv.
func venvScript(dataDir, venvName, scriptName string) string {
	if runtime.GOOS == "windows" {
		return filepath.Join(dataDir, "venvs", venvName, "Scripts", scriptName+".exe")
	}
	return filepath.Join(dataDir, "venvs", venvName, "bin", scriptName)
}

// ensureDirs creates all required subdirectories under dataDir.
func ensureDirs(dataDir string) error {
	for _, sub := range []string{"data", "logs", "config", "venvs"} {
		if err := os.MkdirAll(filepath.Join(dataDir, sub), 0o755); err != nil {
			return err
		}
	}
	return nil
}
