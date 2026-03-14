package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// AppVersion is injected at build time via -ldflags "-X main.AppVersion=x.y.z".
var AppVersion string

// DefaultAppType is injected at build time via -ldflags "-X main.DefaultAppType=cajero".
var DefaultAppType string

func main() {
	// Determine app type:
	// 1. If the executable name contains "owner" → owner app.
	// 2. If --owner flag is passed → owner app.
	// 3. Otherwise fall back to DefaultAppType (from ldflags), default "cajero".
	ownerFlag := flag.Bool("owner", false, "Instalar la aplicacion del propietario")
	flag.Parse()

	appType := DefaultAppType
	if appType == "" {
		appType = AppCajero
	}

	execName := strings.ToLower(filepath.Base(os.Args[0]))
	if strings.Contains(execName, "owner") || *ownerFlag {
		appType = AppOwner
	}

	err := windowsUI(appType, func(
		setStatus func(string),
		setProgress func(pct int),
	) error {
		// Step 0: ask install mode (only for cajero — owner never installs backend).
		installMode := InstallPrincipal
		if appType == AppCajero {
			installMode = askInstallMode()
		}

		// Step 1: fetch manifest.
		setStatus("Conectando con el servidor...")
		version, downloadURL, err := FetchManifest(appType)
		if err != nil {
			return fmt.Errorf("no se pudo obtener el manifiesto: %w", err)
		}

		showBanner(appType, version)

		// Step 2: download installer.
		ext := ".deb"
		if runtime.GOOS == "windows" {
			ext = ".exe"
		}
		prefix := "posvendelo"
		if appType == AppOwner {
			prefix = "posvendelo-owner"
		}

		// Detect extension from the download URL.
		urlLower := strings.ToLower(downloadURL)
		switch {
		case strings.HasSuffix(urlLower, ".exe"):
			ext = ".exe"
		case strings.HasSuffix(urlLower, ".appimage"):
			ext = ".AppImage"
		case strings.HasSuffix(urlLower, ".deb"):
			ext = ".deb"
		}

		destName := fmt.Sprintf("%s-v%s%s", prefix, version, ext)
		destPath := filepath.Join(os.TempDir(), destName)

		setStatus(fmt.Sprintf("Descargando v%s...", version))

		progress := func(downloaded, total int64) {
			if total > 0 {
				pct := int(downloaded * 100 / total)
				dlMB := float64(downloaded) / (1024 * 1024)
				totalMB := float64(total) / (1024 * 1024)
				setStatus(fmt.Sprintf("Descargando v%s... %d%% (%.0f MB / %.0f MB)",
					version, pct, dlMB, totalMB))
				setProgress(pct)
			} else {
				dlMB := float64(downloaded) / (1024 * 1024)
				setStatus(fmt.Sprintf("Descargando v%s... %.0f MB", version, dlMB))
			}
		}

		if err := Download(downloadURL, destPath, progress); err != nil {
			return fmt.Errorf("descarga fallida: %w", err)
		}

		setProgress(100)

		// Step 3: launch installer.
		if installMode == InstallClient {
			setStatus("Instalando como caja secundaria...")
		} else {
			setStatus("Abriendo instalador...")
		}
		if err := Launch(destPath, installMode); err != nil {
			return fmt.Errorf("no se pudo abrir el instalador: %w", err)
		}

		return nil
	})

	if err != nil {
		showError(err.Error())
		os.Exit(1)
	}
}
