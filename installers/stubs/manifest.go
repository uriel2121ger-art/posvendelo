package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"runtime"
	"time"
)

// artifactEntry represents a single downloadable artifact from the manifest.
type artifactEntry struct {
	TargetRef string `json:"target_ref"`
	Version   string `json:"version"`
}

// manifestArtifacts holds the relevant artifact keys from the API response.
type manifestArtifacts struct {
	App      *artifactEntry `json:"app"`
	OwnerApp *artifactEntry `json:"owner_app"`
}

// manifestData wraps the artifacts block.
type manifestData struct {
	Artifacts manifestArtifacts `json:"artifacts"`
}

// manifestResponse is the top-level API envelope.
type manifestResponse struct {
	Success bool         `json:"success"`
	Data    manifestData `json:"data"`
}

// FetchManifest retrieves the latest release metadata from the control-plane.
// appType must be AppCajero or AppOwner.
// Returns the version string and the direct download URL for the installer.
func FetchManifest(appType string) (version string, downloadURL string, err error) {
	osParam := "linux"
	if runtime.GOOS == "windows" {
		osParam = "windows"
	}

	reqURL, err := url.Parse(ManifestURL)
	if err != nil {
		return "", "", fmt.Errorf("URL invalida del manifiesto: %w", err)
	}
	q := reqURL.Query()
	q.Set("os", osParam)
	reqURL.RawQuery = q.Encode()

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Get(reqURL.String())
	if err != nil {
		return "", "", fmt.Errorf("error al conectar con el servidor: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", "", fmt.Errorf("servidor respondio con estado %d", resp.StatusCode)
	}

	// Limit manifest response to 1 MB to prevent OOM from malformed responses.
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return "", "", fmt.Errorf("error al leer respuesta: %w", err)
	}

	var manifest manifestResponse
	if err := json.Unmarshal(body, &manifest); err != nil {
		return "", "", fmt.Errorf("respuesta del servidor no valida: %w", err)
	}

	if !manifest.Success {
		return "", "", fmt.Errorf("el servidor reporto un error en el manifiesto")
	}

	var entry *artifactEntry
	switch appType {
	case AppOwner:
		entry = manifest.Data.Artifacts.OwnerApp
	default:
		entry = manifest.Data.Artifacts.App
	}

	if entry == nil {
		return "", "", fmt.Errorf("artefacto no encontrado en el manifiesto para: %s", appType)
	}
	if entry.TargetRef == "" {
		return "", "", fmt.Errorf("URL de descarga vacia en el manifiesto")
	}
	if entry.Version == "" {
		return "", "", fmt.Errorf("version vacia en el manifiesto")
	}

	return entry.Version, entry.TargetRef, nil
}
