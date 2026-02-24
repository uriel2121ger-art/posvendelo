====================================================
FIX TOASTMANAGER - TITAN POS
====================================================

PROBLEMA CORREGIDO:
-------------------
TypeError: ToastManager.warning() got an unexpected keyword argument 'duration'

Este error aparecia cuando se escaneaba un producto que no existe
en el catalogo.


ARCHIVOS INCLUIDOS:
-------------------
- toast.py          : Archivo corregido
- instalar_fix.sh   : Script de instalacion automatica
- README.txt        : Este archivo


INSTALACION AUTOMATICA (Recomendada):
-------------------------------------
1. Copia esta carpeta a la PC de Lupita
2. Abre una terminal en esta carpeta
3. Ejecuta:

   chmod +x instalar_fix.sh
   ./instalar_fix.sh

4. Reinicia TITAN POS


INSTALACION MANUAL:
-------------------
1. Copia el archivo toast.py a:
   /home/lupita/Escritorio/titan_dist/app/ui/components/toast.py

2. Reinicia TITAN POS


QUE SE CORRIGIO:
----------------
Se agrego el parametro 'duration' al metodo ToastManager.warning()
para que sea compatible con las llamadas que usan auto-cierre.

Antes:  warning(title, message, actions, parent)
Ahora:  warning(title, message, actions, parent, duration=0)

- duration=0    : No se cierra automaticamente (comportamiento original)
- duration=3000 : Se cierra despues de 3 segundos


Fecha: 2026-02-03
====================================================
