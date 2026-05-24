package main

import (
	"context"
	"fmt"
	"path/filepath"

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
	dataDir string
	manager *ProcessManager
}

func NewApp() *App {
	dataDir := appDataDir()
	logDir := filepath.Join(dataDir, "logs")
	return &App{
		dataDir: dataDir,
		manager: NewProcessManager(dataDir, logDir),
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	a.initSystray()
}

// domReady fires after the WebView DOM is loaded and event listeners are registered.
// Starting the sequence here avoids losing early EventsEmit calls.
func (a *App) domReady(_ context.Context) {
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
	// Step 1: ensure data/log/config dirs exist
	if err := ensureDirs(a.dataDir); err != nil {
		a.emitErr(fmt.Sprintf("Failed to create data directories: %v", err))
		return
	}

	// Step 2: port conflict detection
	a.emit("checking", "Checking for port conflicts…", 5)
	if conflicts := checkPortConflicts(); len(conflicts) > 0 {
		a.emitErr(fmt.Sprintf("Ports %v already in use. Close other applications and restart.", conflicts))
		return
	}

	// Step 3: prerequisites (stub — implemented in Phase 3)
	a.emit("checking", "Checking prerequisites…", 20)

	// Step 4: first-launch setup (stub — implemented in Phase 3)
	a.emit("setup", "Checking installation…", 40)

	// Step 5: spawn services with progress callback
	if err := a.manager.Start(func(pct int, msg string) {
		a.emit("starting", msg, pct)
	}); err != nil {
		a.emitErr(fmt.Sprintf("Failed to start services: %v", err))
		return
	}

	// Step 6: navigate WebView to the running app
	a.emit("ready", "Ready!", 100)
	runtime.EventsEmit(a.ctx, "navigate", fmt.Sprintf("http://localhost:%d", appPort))

	// Monitor for post-launch crashes in the background
	go a.watchCrashes()
}

// watchCrashes surfaces fatal sidecar errors to the user after successful launch.
func (a *App) watchCrashes() {
	select {
	case err := <-a.manager.ErrCh():
		runtime.WindowShow(a.ctx)
		a.emitErr(fmt.Sprintf("A service crashed and could not be restarted: %v", err))
	case <-a.ctx.Done():
	}
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
