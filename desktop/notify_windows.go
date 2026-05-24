//go:build windows

package main

import toast "git.sr.ht/~jackmordaunt/go-toast/v2"

// notifyCrash sends a Windows toast notification when a sidecar crashes
// permanently (after exhausting its restart budget). The notification appears
// in the system tray / Action Centre even if the app window is minimised.
// Errors are silently ignored — the error is also surfaced in-app via emitErr.
func notifyCrash(msg string) {
	n := toast.Notification{
		AppID: "pypsa-desktop",
		Title: "pypsa-desktop — service crashed",
		Body:  msg,
	}
	_ = n.Push()
}
