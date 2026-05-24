package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"text/template"
)

// dispatchConfigTmpl is the snakedispatch.yaml written on every launch (idempotent).
// Top-level key is the backend type ("local") — not wrapped under "backends:".
// DATA_DIR sets the job-data directory; pixi_path is re-resolved each launch.
const dispatchConfigTmpl = `# snakedispatch local backend — managed by pypsa-desktop, do not edit manually.
# Regenerated on each launch.
local:
  scratch_dir: "{{ .ScratchDir }}"
  pixi_path: "{{ .PixiPath }}"
  poll_interval: 5
  default_snakemake_args: ["--cores", "1"]
DATA_DIR: "{{ .DataDir }}"
`

// writeDispatchConfig writes snakedispatch.yaml to <dataDir>/config/.
// Safe to call on every launch.
func writeDispatchConfig(dataDir string) error {
	pixiPath, err := exec.LookPath("pixi")
	if err != nil {
		pixiPath = "pixi" // will fail loudly at runtime if truly absent
	}

	data := struct {
		ScratchDir string
		PixiPath   string
		DataDir    string
	}{
		ScratchDir: filepath.ToSlash(filepath.Join(dataDir, "snakedispatch")),
		PixiPath:   filepath.ToSlash(pixiPath),
		DataDir:    filepath.ToSlash(filepath.Join(dataDir, "snakedispatch")),
	}

	configPath := filepath.Join(dataDir, "config", "snakedispatch.yaml")
	f, err := os.Create(configPath)
	if err != nil {
		return fmt.Errorf("create snakedispatch.yaml: %w", err)
	}
	defer f.Close()

	tmpl, err := template.New("cfg").Parse(dispatchConfigTmpl)
	if err != nil {
		return err
	}
	return tmpl.Execute(f, data)
}
