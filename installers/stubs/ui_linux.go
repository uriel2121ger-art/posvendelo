//go:build !windows

package main

import (
	"fmt"
	"strings"
)

// windowsUI is only defined on Windows. On Linux the flow is driven directly
// from main without a message pump, so this function just calls run().
func windowsUI(appType string, run func(
	setStatus func(string),
	setProgress func(pct int),
) error) error {
	setStatus := func(text string) {
		fmt.Printf("\r\033[K%s", text) // \033[K = clear to end of line
	}
	setProgress := func(_ int) {
		// No-op on Linux — setStatus already includes percentage and MB info.
	}
	err := run(setStatus, setProgress)
	fmt.Println() // newline after \r progress
	return err
}

// showBanner prints a simple ASCII banner to the terminal.
func showBanner(appType, version string) {
	label := "PosVendelo"
	if appType == AppOwner {
		label = "PosVendelo Owner"
	}
	vStr := ""
	if version != "" {
		vStr = " v" + version
	}
	fmt.Printf("\n  %s%s — Instalador\n", label, vStr)
	fmt.Println("  " + strings.Repeat("─", 38))
}

// showError prints an error message to the terminal.
func showError(errMsg string) {
	fmt.Printf("\n\nError: %s\n", errMsg)
}

// askInstallMode prompts the user in the terminal to choose principal or client.
func askInstallMode() string {
	fmt.Println("\n  ¿Como se usara esta PC?")
	fmt.Println("  1) PC Principal — instala servidor y base de datos")
	fmt.Println("  2) Caja secundaria — se conecta a otro servidor en la red")
	fmt.Print("\n  Elige [1/2] (default 1): ")

	var input string
	fmt.Scanln(&input)
	input = strings.TrimSpace(input)
	if input == "2" {
		return InstallClient
	}
	return InstallPrincipal
}
