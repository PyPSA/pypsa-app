package main

// Setup handles first-launch venv creation and package installation.
// Stub in Phase 1; implemented in Phase 3.
type Setup struct{}

func NewSetup() *Setup { return &Setup{} }

// IsComplete returns true when both venvs exist (sentinel file check).
func (s *Setup) IsComplete() bool { return true }

// Run executes first-launch setup, reporting progress via the callback.
func (s *Setup) Run(progress func(pct int, msg string)) error { return nil }
