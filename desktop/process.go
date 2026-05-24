package main

import (
	"fmt"
	"net"
	"time"
)

// ProcessManager handles spawning and stopping the pypsa-app and snakedispatch sidecars.
// Stub in Phase 1; fully implemented in Phase 2.
type ProcessManager struct{}

func NewProcessManager() *ProcessManager { return &ProcessManager{} }

func (pm *ProcessManager) Start() error { return nil }
func (pm *ProcessManager) Stop()        {}

func isPortInUse(port int) bool {
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("127.0.0.1:%d", port), 200*time.Millisecond)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

func checkPortConflicts() []int {
	ports := []int{8765, 8766}
	var taken []int
	for _, p := range ports {
		if isPortInUse(p) {
			taken = append(taken, p)
		}
	}
	return taken
}
