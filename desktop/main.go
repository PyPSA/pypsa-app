package main

import (
	"embed"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/windows"
)

//go:embed all:frontend/dist
var assets embed.FS

func main() {
	app := NewApp()

	err := wails.Run(&options.App{
		Title:            "pypsa-desktop",
		Width:            640,
		Height:           420,
		DisableResize:    true,
		AssetServer:      &assetserver.Options{Assets: assets},
		BackgroundColour: &options.RGBA{R: 17, G: 24, B: 39, A: 1},
		OnStartup:        app.startup,
		OnDomReady:       app.domReady,
		OnShutdown:       app.shutdown,
		OnBeforeClose:    app.beforeClose,
		HideWindowOnClose: true,
		Bind:             []interface{}{app},
		Windows: &windows.Options{
			WebviewIsTransparent: false,
			WindowIsTranslucent:  false,
		},
	})

	if err != nil {
		println("Error:", err.Error())
	}
}
