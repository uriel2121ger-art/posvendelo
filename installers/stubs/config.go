package main

// ManifestURL is the control-plane endpoint that returns download metadata.
const ManifestURL = "https://posvendelo.com/api/v1/releases/manifest"

// AppCajero identifies the cashier POS application.
const AppCajero = "cajero"

// AppOwner identifies the owner management application.
const AppOwner = "owner"

// Install mode: principal installs backend+DB, client skips it (secondary POS).
const (
	InstallPrincipal = "principal"
	InstallClient    = "client"
)
