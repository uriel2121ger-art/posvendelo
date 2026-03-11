#!/usr/bin/env bash
# generate-license-keypair.sh
# Generates an RSA 2048 keypair for signing TITAN POS licenses.
#
# Usage:
#   bash scripts/generate-license-keypair.sh
#
# Output:
#   - license_private.pem  : private key (keep secret, never commit)
#   - license_public.pem   : public key  (distribute to nodes / embed in firmware)
#   - Prints the CP_LICENSE_PRIVATE_KEY= line ready to paste into .env
#
# Requirements: openssl (available on Linux/macOS without sudo)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}"

PRIVATE_PEM="${OUTPUT_DIR}/license_private.pem"
PUBLIC_PEM="${OUTPUT_DIR}/license_public.pem"

# ── Sanity checks ─────────────────────────────────────────────────────────────
if ! command -v openssl &>/dev/null; then
  echo "ERROR: openssl not found. Install it with: sudo apt install openssl" >&2
  exit 1
fi

if [[ -f "${PRIVATE_PEM}" ]]; then
  echo ""
  echo "WARNING: ${PRIVATE_PEM} already exists."
  echo "Generating a NEW key will invalidate ALL previously signed licenses."
  echo ""
  read -r -p "Continue and overwrite? [y/N] " confirm
  if [[ "${confirm,,}" != "y" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# ── Key generation ────────────────────────────────────────────────────────────
echo ""
echo "Generating RSA 2048 private key..."
openssl genrsa -out "${PRIVATE_PEM}" 2048 2>/dev/null
chmod 600 "${PRIVATE_PEM}"

echo "Extracting public key..."
openssl rsa -in "${PRIVATE_PEM}" -pubout -out "${PUBLIC_PEM}" 2>/dev/null
chmod 644 "${PUBLIC_PEM}"

# ── Produce single-line env var value (newlines -> literal \n) ────────────────
PRIVATE_KEY_ONELINER="$(awk 'NF {printf "%s\\n", $0}' "${PRIVATE_PEM}")"

# ── Output ────────────────────────────────────────────────────────────────────
echo ""
echo "========================================================================"
echo "  TITAN POS — License keypair generated"
echo "========================================================================"
echo ""
echo "Files written:"
echo "  Private key : ${PRIVATE_PEM}"
echo "  Public key  : ${PUBLIC_PEM}"
echo ""
echo "------------------------------------------------------------------------"
echo "  STEP 1 — Add this line to control-plane/.env (or root .env):"
echo "------------------------------------------------------------------------"
echo ""
echo "CP_LICENSE_PRIVATE_KEY=${PRIVATE_KEY_ONELINER}"
echo ""
echo "------------------------------------------------------------------------"
echo "  STEP 2 — Set strict mode so the server refuses to start without a key:"
echo "------------------------------------------------------------------------"
echo ""
echo "CP_LICENSE_KEY_STRICT=true"
echo ""
echo "------------------------------------------------------------------------"
echo "  STEP 3 — Distribute the PUBLIC key to nodes (embed in license validator):"
echo "------------------------------------------------------------------------"
echo ""
cat "${PUBLIC_PEM}"
echo ""
echo "========================================================================"
echo "  SECURITY REMINDERS"
echo "  - NEVER commit license_private.pem to git."
echo "  - Store the private key in a secrets manager (Vault, AWS SM, etc.)."
echo "  - Keep license_public.pem safe to share but ensure authenticity."
echo "  - Rotate the keypair by re-running this script, then re-issuing all"
echo "    active licenses (existing signed licenses will become invalid)."
echo "========================================================================"
echo ""
