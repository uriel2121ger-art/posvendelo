#!/usr/bin/env bash
# Wrapper para doble clic — lanzado por INSTALAR.desktop
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
bash setup.sh
read -rp "Presiona Enter para cerrar..."
