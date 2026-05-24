package main

import "os/exec"

// PrereqResult describes the detection result for a single prerequisite.
type PrereqResult struct {
	Name    string `json:"name"`
	Found   bool   `json:"found"`
	Message string `json:"message,omitempty"`
}

// CheckPrereqs detects Git and Pixi on PATH.
// Called during startup; missing tools produce warnings in the splash screen.
func CheckPrereqs() []PrereqResult {
	return []PrereqResult{
		checkTool("Git", "git"),
		checkTool("Pixi", "pixi"),
	}
}

func checkTool(name, cmd string) PrereqResult {
	if _, err := exec.LookPath(cmd); err != nil {
		return PrereqResult{Name: name, Found: false, Message: cmd + " not found in PATH"}
	}
	return PrereqResult{Name: name, Found: true}
}
