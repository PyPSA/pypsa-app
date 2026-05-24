//go:build !windows

package main

// notifyCrash is a no-op on non-Windows platforms. Crash events are surfaced
// via the in-app error state and the WebView window being brought to the front.
func notifyCrash(_ string) {}
