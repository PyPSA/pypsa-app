//go:build windows

package main

import (
	"os"
	"syscall"
	"time"
)

func terminateProcess(p *os.Process) {
	ch := make(chan struct{})
	go func() { p.Wait(); close(ch) }() //nolint:errcheck

	// CTRL_BREAK_EVENT reaches processes started in a new process group.
	dll := syscall.MustLoadDLL("kernel32.dll")
	ctrl := dll.MustFindProc("GenerateConsoleCtrlEvent")
	ctrl.Call(uintptr(syscall.CTRL_BREAK_EVENT), uintptr(p.Pid)) //nolint:errcheck

	select {
	case <-ch:
	case <-time.After(shutdownTimeout):
		p.Kill() //nolint:errcheck
	}
}

func newProcessGroup() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP}
}
