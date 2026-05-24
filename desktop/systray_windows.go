//go:build windows

package main

import (
	_ "embed"

	"github.com/energye/systray"
)

//go:embed build/appicon.png
var trayIcon []byte

func (a *App) initSystray() {
	go systray.Run(func() {
		systray.SetIcon(trayIcon)
		systray.SetTooltip("pypsa-desktop")

		mShow := systray.AddMenuItem("Show Window", "Show the main window")
		mShow.Click(func() { a.ShowWindow() })

		systray.AddSeparator()

		mQuit := systray.AddMenuItem("Quit", "Quit pypsa-desktop")
		mQuit.Click(func() {
			systray.Quit()
			a.Quit()
		})
	}, func() {})
}
