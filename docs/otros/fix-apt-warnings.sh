#!/bin/bash
# Arregla avisos de apt: repos duplicados y Signed-By
# Ejecutar: sudo bash docs/fix-apt-warnings.sh

set -e

echo "=== 1. Quitar duplicado antigravity (mantener solo .sources) ==="
if [ -f /etc/apt/sources.list.d/antigravity.list ]; then
  sudo mv /etc/apt/sources.list.d/antigravity.list /etc/apt/sources.list.d/antigravity.list.disabled
  echo "  antigravity.list desactivado (el repo sigue en antigravity.sources)."
else
  echo "  antigravity.list ya no existe, nada que hacer."
fi

echo ""
echo "=== 2. Opcional: quitar aviso Signed-By de netdevops.fury.site ==="
echo "  El repo usa Trusted: yes. Para quitar el Notice de Signed-By hay que"
echo "  tener la clave GPG del repo en /etc/apt/keyrings/ y poner en"
echo "  /etc/apt/sources.list.d/netdevops.sources la línea:"
echo "  Signed-By: /etc/apt/keyrings/netdevops.gpg"
echo "  Si no tienes la clave, el Notice es inofensivo."
echo ""

echo "=== 3. Actualizar apt ==="
sudo apt-get update 2>&1 | tail -5

echo ""
echo "Listo. Vuelve a ejecutar 'sudo apt update' y no deberían salir los warnings de antigravity."
