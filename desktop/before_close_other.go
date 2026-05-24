//go:build !windows

package main

import "context"

// beforeClose allows the window to close normally on non-Windows platforms.
// No systray exists on macOS/Linux, so hiding would strand the app with no UI.
func (a *App) beforeClose(_ context.Context) bool {
	return false
}
