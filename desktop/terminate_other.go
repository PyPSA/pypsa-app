//go:build !windows

package main

import (
	"os"
	"syscall"
	"time"
)

func terminateProcess(p *os.Process) {
	ch := make(chan struct{})
	go func() { p.Wait(); close(ch) }() //nolint:errcheck

	p.Signal(syscall.SIGTERM) //nolint:errcheck

	select {
	case <-ch:
	case <-time.After(shutdownTimeout):
		p.Kill() //nolint:errcheck
	}
}

func newProcessGroup() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{Setpgid: true}
}
