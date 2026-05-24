package main

import (
	"context"
	"fmt"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// StatusEvent is sent to the frontend on each startup step.
type StatusEvent struct {
	Phase   string `json:"phase"`
	Message string `json:"message"`
	Pct     int    `json:"pct"`
	Err     string `json:"err,omitempty"`
}

// App is the Wails application struct (control plane).
type App struct {
	ctx     context.Context
	manager *ProcessManager
}

func NewApp() *App {
	return &App{
		manager: NewProcessManager(),
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	a.initSystray()
	go a.runStartupSequence()
}

func (a *App) shutdown(_ context.Context) {
	a.manager.Stop()
}

// beforeClose hides the window instead of quitting when the user clicks X.
func (a *App) beforeClose(ctx context.Context) bool {
	runtime.WindowHide(ctx)
	return true // returning true cancels the default close
}

func (a *App) emit(phase, msg string, pct int) {
	runtime.EventsEmit(a.ctx, "status", StatusEvent{Phase: phase, Message: msg, Pct: pct})
}

func (a *App) emitErr(msg string) {
	runtime.EventsEmit(a.ctx, "status", StatusEvent{Phase: "error", Message: msg, Pct: 0, Err: msg})
}

func (a *App) runStartupSequence() {
	// Step 1: port conflict detection
	a.emit("checking", "Checking for port conflicts…", 5)
	if conflicts := checkPortConflicts(); len(conflicts) > 0 {
		a.emitErr(fmt.Sprintf("Ports %v already in use. Close other applications and restart.", conflicts))
		return
	}

	// Step 2: prerequisites (stub — implemented in Phase 3)
	a.emit("checking", "Checking prerequisites…", 20)
	time.Sleep(150 * time.Millisecond)

	// Step 3: first-launch setup (stub — implemented in Phase 3)
	a.emit("setup", "Checking installation…", 40)
	time.Sleep(150 * time.Millisecond)

	// Step 4: start services (stub — implemented in Phase 2)
	a.emit("starting", "Starting services…", 70)
	time.Sleep(150 * time.Millisecond)

	// Step 5: navigate WebView to the running app
	a.emit("ready", "Ready!", 100)
	time.Sleep(300 * time.Millisecond)
	runtime.EventsEmit(a.ctx, "navigate", "http://localhost:8765")
}

// Quit stops services and exits the application.
// Callable from the system tray and frontend.
func (a *App) Quit() {
	a.manager.Stop()
	runtime.Quit(a.ctx)
}

// ShowWindow brings the main window to the foreground.
// Callable from the system tray.
func (a *App) ShowWindow() {
	runtime.WindowShow(a.ctx)
}
