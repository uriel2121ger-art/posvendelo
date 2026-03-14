package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

// Download fetches url and writes it to destPath via a temporary file.
// progress is called periodically with (bytesDownloaded, totalBytes).
// totalBytes is -1 when the server does not send Content-Length.
func Download(url string, destPath string, progress func(downloaded, total int64)) error {
	client := &http.Client{
		Transport: &http.Transport{
			DialContext:           (&net.Dialer{Timeout: 30 * time.Second}).DialContext,
			TLSHandshakeTimeout:  15 * time.Second,
			ResponseHeaderTimeout: 30 * time.Second,
		},
		// No overall Timeout — large downloads may take minutes.
	}
	resp, err := client.Get(url)
	if err != nil {
		return fmt.Errorf("error al iniciar descarga: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("servidor respondio con estado %d al descargar", resp.StatusCode)
	}

	total := resp.ContentLength // -1 if unknown

	// Write to a temp file in the same directory as destPath so the rename is atomic.
	dir := filepath.Dir(destPath)
	tmp, err := os.CreateTemp(dir, "posvendelo-stub-*.tmp")
	if err != nil {
		return fmt.Errorf("no se pudo crear archivo temporal: %w", err)
	}
	tmpPath := tmp.Name()

	// Ensure the temp file is cleaned up on error.
	closed := false
	defer func() {
		if !closed {
			tmp.Close()
		}
		// Only remove temp if we didn't successfully rename it.
		if _, err := os.Stat(tmpPath); err == nil {
			os.Remove(tmpPath)
		}
	}()

	const chunkSize = 32 * 1024 // 32 KB read buffer
	buf := make([]byte, chunkSize)
	var downloaded int64

	for {
		n, err := resp.Body.Read(buf)
		if n > 0 {
			if _, werr := tmp.Write(buf[:n]); werr != nil {
				return fmt.Errorf("error al escribir en disco: %w", werr)
			}
			downloaded += int64(n)
			if progress != nil {
				progress(downloaded, total)
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("error durante la descarga: %w", err)
		}
	}

	if err := tmp.Close(); err != nil {
		return fmt.Errorf("error al cerrar archivo temporal: %w", err)
	}
	closed = true

	if err := os.Rename(tmpPath, destPath); err != nil {
		return fmt.Errorf("error al mover instalador a destino: %w", err)
	}

	return nil
}
