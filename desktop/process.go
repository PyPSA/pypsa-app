package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"gopkg.in/natefinch/lumberjack.v2"
)

const (
	appPort         = 8765
	dispatchPort    = 8766
	healthTimeout   = 60 * time.Second
	pollInterval    = 500 * time.Millisecond
	maxRestarts     = 3
	shutdownTimeout = 5 * time.Second
)

// Sidecar is a managed subprocess with automatic crash-recovery.
type Sidecar struct {
	Name    string
	mk      func() *exec.Cmd // factory; rebuilt on each restart
	log     *lumberjack.Logger
	mu      sync.Mutex
	cmd     *exec.Cmd
	restart int
	stopped bool
}

// ProcessManager owns both sidecars and their full lifecycle.
type ProcessManager struct {
	dataDir  string
	logDir   string
	ctx      context.Context
	cancel   context.CancelFunc
	dispatch *Sidecar
	app      *Sidecar
	errCh    chan error
}

func NewProcessManager(dataDir, logDir string) *ProcessManager {
	ctx, cancel := context.WithCancel(context.Background())
	return &ProcessManager{
		dataDir: dataDir,
		logDir:  logDir,
		ctx:     ctx,
		cancel:  cancel,
		errCh:   make(chan error, 2),
	}
}

// Start launches snakedispatch then pypsa-app, health-polling each before proceeding.
// progress(pct, msg) is called at each step so the splash screen stays updated.
func (pm *ProcessManager) Start(progress func(pct int, msg string)) error {
	progress(55, "Starting snakedispatch…")
	sd, err := pm.spawnSidecar("snakedispatch", pm.dispatchCmd)
	if err != nil {
		return fmt.Errorf("launch snakedispatch: %w", err)
	}
	pm.dispatch = sd

	progress(65, "Waiting for snakedispatch…")
	if err := pm.pollHealth(dispatchPort); err != nil {
		return err
	}

	progress(78, "Starting pypsa-app…")
	ap, err := pm.spawnSidecar("pypsa-app", pm.pypsaCmd)
	if err != nil {
		return fmt.Errorf("launch pypsa-app: %w", err)
	}
	pm.app = ap

	progress(90, "Waiting for pypsa-app…")
	if err := pm.pollHealth(appPort); err != nil {
		return err
	}

	return nil
}

// Stop gracefully terminates both sidecars (pypsa-app first, then snakedispatch).
func (pm *ProcessManager) Stop() {
	pm.cancel()
	pm.stopSidecar(pm.app)
	pm.stopSidecar(pm.dispatch)
}

// ErrCh receives a fatal error when a sidecar exhausts its restart budget.
func (pm *ProcessManager) ErrCh() <-chan error { return pm.errCh }

// -- internal --

func (pm *ProcessManager) spawnSidecar(name string, mk func() *exec.Cmd) (*Sidecar, error) {
	lj := &lumberjack.Logger{
		Filename:   filepath.Join(pm.logDir, name+".log"),
		MaxSize:    10,
		MaxBackups: 3,
	}
	cmd := mk()
	cmd.Stdout = lj
	cmd.Stderr = lj
	cmd.SysProcAttr = newProcessGroup()

	if err := cmd.Start(); err != nil {
		return nil, err
	}
	s := &Sidecar{Name: name, mk: mk, log: lj, cmd: cmd}
	go pm.watch(s)
	return s, nil
}

// watch monitors s and restarts it on unexpected exit, up to maxRestarts times.
func (pm *ProcessManager) watch(s *Sidecar) {
	for {
		waitErr := s.cmd.Wait()

		s.mu.Lock()
		if s.stopped {
			s.mu.Unlock()
			return
		}
		s.restart++
		n := s.restart
		if n > maxRestarts {
			s.mu.Unlock()
			pm.errCh <- fmt.Errorf("%s crashed %d times; last: %v", s.Name, n, waitErr)
			return
		}
		s.mu.Unlock()

		select {
		case <-pm.ctx.Done():
			return
		case <-time.After(time.Duration(n) * time.Second):
		}

		cmd := s.mk()
		cmd.Stdout = s.log
		cmd.Stderr = s.log
		cmd.SysProcAttr = newProcessGroup()

		s.mu.Lock()
		if startErr := cmd.Start(); startErr != nil {
			s.mu.Unlock()
			pm.errCh <- fmt.Errorf("%s restart %d failed: %w", s.Name, n, startErr)
			return
		}
		s.cmd = cmd
		s.mu.Unlock()
	}
}

func (pm *ProcessManager) stopSidecar(s *Sidecar) {
	if s == nil {
		return
	}
	s.mu.Lock()
	s.stopped = true
	cmd := s.cmd
	s.mu.Unlock()

	if cmd == nil || cmd.Process == nil {
		return
	}
	terminateProcess(cmd.Process)
}

func (pm *ProcessManager) pollHealth(port int) error {
	client := &http.Client{Timeout: 2 * time.Second}
	url := fmt.Sprintf("http://127.0.0.1:%d/health", port)
	deadline := time.Now().Add(healthTimeout)

	for time.Now().Before(deadline) {
		select {
		case <-pm.ctx.Done():
			return pm.ctx.Err()
		default:
		}
		resp, err := client.Get(url)
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode < 500 {
				return nil
			}
		}
		time.Sleep(pollInterval)
	}
	return fmt.Errorf("service on :%d not healthy within %s", port, healthTimeout)
}

// pypsaCmd builds a fresh exec.Cmd for pypsa-app.
// We use "serve" (not "open") so we can set SNAKEDISPATCH_BACKENDS.
// "open" forces LOCAL_MODE=true which blocks that env var, hiding the Runs view.
func (pm *ProcessManager) pypsaCmd() *exec.Cmd {
	cmd := exec.Command(
		venvScript(pm.dataDir, "pypsa-app", "pypsa-app"),
		"serve",
		"--host", "127.0.0.1",
		"--port", fmt.Sprintf("%d", appPort),
	)
	cmd.Env = append(filterEnv("SNAKEDISPATCH_BACKENDS"),
		"ENABLE_AUTH=false",
		"SNAKEDISPATCH_BACKENDS=local=http://127.0.0.1:"+fmt.Sprintf("%d", dispatchPort),
		"DATA_DIR="+filepath.Join(pm.dataDir, "data"),
		"DATABASE_URL=sqlite:///"+filepath.Join(pm.dataDir, "data", "pypsa-app.db"),
	)
	return cmd
}

// filterEnv returns os.Environ() with the given keys removed.
func filterEnv(strip ...string) []string {
	blocked := make(map[string]bool, len(strip))
	for _, k := range strip {
		blocked[k] = true
	}
	env := os.Environ()
	out := make([]string, 0, len(env))
	for _, e := range env {
		key := e
		if i := strings.IndexByte(e, '='); i >= 0 {
			key = e[:i]
		}
		if !blocked[key] {
			out = append(out, e)
		}
	}
	return out
}

// dispatchCmd builds a fresh exec.Cmd for snakedispatch.
// snakedispatch has no console script; it is started via uvicorn directly.
func (pm *ProcessManager) dispatchCmd() *exec.Cmd {
	configPath := filepath.Join(pm.dataDir, "config", "snakedispatch.yaml")
	cmd := exec.Command(
		venvScript(pm.dataDir, "snakedispatch", "uvicorn"),
		"app.main:app",
		"--host", "127.0.0.1",
		"--port", fmt.Sprintf("%d", dispatchPort),
	)
	cmd.Env = append(os.Environ(),
		"SNAKEDISPATCH_CONFIG="+configPath,
		"DATA_DIR="+filepath.Join(pm.dataDir, "snakedispatch"),
	)
	return cmd
}

func isPortInUse(port int) bool {
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("127.0.0.1:%d", port), 200*time.Millisecond)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

func checkPortConflicts() []int {
	ports := []int{appPort, dispatchPort, proxyPort}
	var taken []int
	for _, p := range ports {
		if isPortInUse(p) {
			taken = append(taken, p)
		}
	}
	return taken
}
