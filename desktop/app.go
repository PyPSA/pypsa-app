package main

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"
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

// domReady fires after the WebView DOM is parsed but the JS onMount may not have run yet.
// We wait for a "frontend:ready" signal from Svelte (emitted after EventsOn is registered),
// with a 500 ms fallback so we never get stuck if the event is missed.
func (a *App) domReady(_ context.Context) {
	ready := make(chan struct{}, 1)
	runtime.EventsOnce(a.ctx, "frontend:ready", func(...interface{}) {
		select {
		case ready <- struct{}{}:
		default:
		}
	})
	go func() {
		select {
		case <-ready:
		case <-time.After(500 * time.Millisecond):
		}
		a.runStartupSequence()
	}()
}

func (a *App) shutdown(_ context.Context) {
	a.manager.Stop()
}

func (a *App) emit(phase, msg string, pct int) {
	runtime.EventsEmit(a.ctx, "status", StatusEvent{Phase: phase, Message: msg, Pct: pct})
}

func (a *App) emitErr(msg string) {
	runtime.EventsEmit(a.ctx, "status", StatusEvent{Phase: "error", Message: msg, Pct: 0, Err: msg})
}

func (a *App) runStartupSequence() {
	// 1. Ensure all data/log/config directories exist
	if err := ensureDirs(a.dataDir); err != nil {
		a.emitErr(fmt.Sprintf("Failed to create data directories: %v", err))
		return
	}

	// 2. Port conflict detection
	a.emit("checking", "Checking for port conflicts…", 5)
	if conflicts := checkPortConflicts(); len(conflicts) > 0 {
		a.emitErr(fmt.Sprintf("Ports %v already in use. Close other applications and restart.", conflicts))
		return
	}

	// 3. Prerequisites — warn but don't fail (Git/Pixi needed only for workflows)
	a.emit("checking", "Checking prerequisites…", 10)
	prereqs := CheckPrereqs()
	var missing []string
	for _, p := range prereqs {
		if !p.Found {
			missing = append(missing, p.Name)
		}
	}
	if len(missing) > 0 {
		a.emit("checking",
			fmt.Sprintf("Warning: %s not found in PATH — Snakemake workflows may fail.",
				strings.Join(missing, ", ")),
			10)
		time.Sleep(2 * time.Second)
	}

	// 4. First-launch setup (create venvs + install packages)
	setup := NewSetup(a.dataDir)
	if !setup.IsComplete() {
		if err := setup.Run(15, 48, func(pct int, msg string) {
			a.emit("setup", msg, pct)
		}); err != nil {
			a.emitErr(fmt.Sprintf(
				"Setup failed: %v\n\nSee %s for details.",
				err, filepath.Join(a.dataDir, "logs", "setup.log"),
			))
			return
		}
	} else {
		a.emit("setup", "Installation verified.", 48)
	}

	// 5. Write snakedispatch config (idempotent — refreshes pixi_path each launch)
	a.emit("setup", "Writing snakedispatch config…", 50)
	if err := writeDispatchConfig(a.dataDir); err != nil {
		a.emitErr(fmt.Sprintf("Failed to write snakedispatch config: %v", err))
		return
	}

	// 6. Spawn services and health-poll each
	if err := a.manager.Start(func(pct int, msg string) {
		a.emit("starting", msg, pct)
	}); err != nil {
		a.emitErr(fmt.Sprintf("Failed to start services: %v", err))
		return
	}

	// 7. Navigate WebView to the running app
	a.emit("ready", "Ready!", 100)
	runtime.EventsEmit(a.ctx, "navigate", fmt.Sprintf("http://localhost:%d", appPort))

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

// Quit stops services and exits. Callable from system tray and frontend.
func (a *App) Quit() {
	a.manager.Stop()
	runtime.Quit(a.ctx)
}

// ShowWindow brings the main window to the foreground. Callable from system tray.
func (a *App) ShowWindow() {
	runtime.WindowShow(a.ctx)
}
