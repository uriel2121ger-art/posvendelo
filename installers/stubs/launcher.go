package main

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// Launch executes the downloaded installer at installerPath.
// installMode is "principal" or "client" — only affects Linux .deb (INSTALL_MODE env var).
// On Windows it starts the .exe via "cmd /c start".
// On Linux it uses pkexec for .deb files or chmod+exec for AppImage.
func Launch(installerPath, installMode string) error {
	switch runtime.GOOS {
	case "windows":
		return launchWindows(installerPath)
	default:
		return launchLinux(installerPath, installMode)
	}
}

func launchWindows(path string) error {
	// Quote the path for cmd.exe to handle spaces and special characters.
	cmd := exec.Command("cmd", "/c", "start", "", `"`+path+`"`)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("no se pudo abrir el instalador: %w", err)
	}
	// Detach — the installer runs independently.
	return nil
}

func launchLinux(path, installMode string) error {
	lower := strings.ToLower(path)

	if strings.HasSuffix(lower, ".deb") {
		var cmd *exec.Cmd
		if os.Geteuid() == 0 {
			cmd = exec.Command("dpkg", "-i", path)
		} else if _, err := exec.LookPath("pkexec"); err == nil {
			// pkexec doesn't propagate env vars, use env(1) to inject INSTALL_MODE.
			cmd = exec.Command("pkexec", "env", fmt.Sprintf("INSTALL_MODE=%s", installMode), "dpkg", "-i", path)
		} else {
			cmd = exec.Command("sudo", "env", fmt.Sprintf("INSTALL_MODE=%s", installMode), "dpkg", "-i", path)
		}
		if os.Geteuid() == 0 {
			cmd.Env = append(os.Environ(), fmt.Sprintf("INSTALL_MODE=%s", installMode))
		}
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Start(); err != nil {
			return fmt.Errorf("no se pudo ejecutar dpkg: %w", err)
		}
		return cmd.Wait()
	}

	// AppImage or other executable
	if err := os.Chmod(path, 0755); err != nil {
		return fmt.Errorf("no se pudo dar permisos de ejecucion: %w", err)
	}
	cmd := exec.Command(path)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("no se pudo ejecutar el instalador: %w", err)
	}
	return nil
}
