# Desplegar control-plane en el homelab (producción)

Cuando cambies la landing o el API del control-plane y quieras ver los cambios en producción (posvendelo.com / catalogopro.mx).

## 1. Desde tu máquina (ya hecho si acabas de hacer push)

```bash
cd "/home/uriel/Documentos/PUNTO DE VENTA"
git add control-plane/main.py control-plane/landing-preview.html
git commit -m "fix(control-plane): nav a ancho completo; landing..."
git push origin master
```

## 2. En el homelab (192.168.10.90)

Depende de cómo tengas el código en el servidor.

### Opción A: El directorio del control-plane es un clone de Git

Si en el homelab tienes un clone del repo (por ejemplo en `/home/uriel/posvendelo-control-plane` con `git remote` apuntando a posvendelo):

**Si el clone es del repo posvendelo y el compose está dentro de `control-plane/`:**
```bash
cd /ruta/al/repo   # ej. /home/uriel/posvendelo-repo o donde tengas el clone
git fetch origin
git merge origin/master --no-edit   # o: git pull origin master
rsync -av control-plane/ /home/uriel/posvendelo-control-plane/ --exclude=.env --exclude=downloads --exclude=__pycache__
cd /home/uriel/posvendelo-control-plane
docker compose build api
docker compose up -d api
```

**Si en el homelab el directorio de deploy ES el clone (por ejemplo `/home/uriel/posvendelo-control-plane` tiene `.git` y es clone de posvendelo con la raíz siendo la carpeta `control-plane`):**
```bash
cd /home/uriel/posvendelo-control-plane
git fetch origin
git pull origin master
docker compose build api
docker compose up -d api
```

### Opción B: Solo copias archivos (sin Git en el directorio de deploy)

Si actualizas copiando archivos desde tu máquina:

```bash
# Desde tu máquina (en "PUNTO DE VENTA")
scp control-plane/main.py control-plane/landing-preview.html usuario@192.168.10.90:/home/uriel/posvendelo-control-plane/
ssh usuario@192.168.10.90 'cd /home/uriel/posvendelo-control-plane && docker compose build api && docker compose up -d api'
```

Sustituye `usuario` por tu usuario SSH en el homelab.

## 3. Comprobar

```bash
curl -s https://posvendelo.com/health
# o por IP:
curl -s http://192.168.10.90:9090/health
```

Abre https://posvendelo.com (o tu dominio) y recarga con Ctrl+Shift+R: el nav debe ir de borde a borde sin franjas negras.
