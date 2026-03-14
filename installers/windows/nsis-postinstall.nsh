; =============================================================================
; POSVENDELO — NSIS custom install/uninstall macros
; Incluido por electron-builder via nsis.include en electron-builder.yml
;
; Ejecuta postinst equivalente al Linux .deb:
;   1. Detecta Docker Desktop; lo descarga e instala si no está presente.
;   2. Crea C:\ProgramData\POSVENDELO\ con .env y docker-compose.yml.
;   3. Corre docker compose pull + up -d.
;   4. Espera el health endpoint (http://127.0.0.1:8000/health).
;   5. Escribe INSTALL_SUMMARY.txt.
; =============================================================================

!macro customInstall

  ; --------------------------------------------------------------------------
  ; Variables locales
  ; --------------------------------------------------------------------------
  Var /GLOBAL POS_DATA_DIR
  Var /GLOBAL POS_COMPOSE
  Var /GLOBAL POS_ENV
  Var /GLOBAL POS_SUMMARY
  Var /GLOBAL DOCKER_EXIT
  Var /GLOBAL HEALTH_ATTEMPTS
  Var /GLOBAL HEALTH_RESULT
  Var /GLOBAL POS_AGENT_DIR
  Var /GLOBAL POS_AGENT_FILE
  Var /GLOBAL POS_LOCAL_APPDATA

  ; NSIS no tiene $PROGRAMDATA built-in — leer de variable de entorno
  ReadEnvStr $POS_DATA_DIR PROGRAMDATA
  StrCmp $POS_DATA_DIR "" 0 +2
    StrCpy $POS_DATA_DIR "C:\ProgramData"
  StrCpy $POS_DATA_DIR "$POS_DATA_DIR\POSVENDELO"
  StrCpy $POS_COMPOSE  "$POS_DATA_DIR\docker-compose.yml"
  StrCpy $POS_ENV      "$POS_DATA_DIR\.env"
  StrCpy $POS_SUMMARY  "$POS_DATA_DIR\INSTALL_SUMMARY.txt"

  ; --------------------------------------------------------------------------
  ; 1. Detectar Docker Desktop
  ; --------------------------------------------------------------------------
  DetailPrint "Verificando Docker Desktop..."
  nsExec::ExecToLog 'cmd /c docker --version'
  Pop $DOCKER_EXIT

  ${If} $DOCKER_EXIT != 0
    DetailPrint "Docker Desktop no encontrado. Descargando instalador..."

    ; Necesita el plugin inetc incluido con NSIS. Si no está disponible,
    ; electron-builder lo incluye con la distribución bundled de NSIS.
    inetc::get \
      "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" \
      "$TEMP\DockerDesktopInstaller.exe" \
      /CAPTION "POSVENDELO — Descargando Docker Desktop" \
      /END

    DetailPrint "Instalando Docker Desktop (puede tardar varios minutos)..."
    nsExec::ExecToLog '"$TEMP\DockerDesktopInstaller.exe" install --quiet --accept-license'
    Pop $0
    Delete "$TEMP\DockerDesktopInstaller.exe"

    ${If} $0 != 0
      MessageBox MB_ICONEXCLAMATION|MB_OK \
        "Docker Desktop no se pudo instalar automáticamente.$\r$\n\
        Por favor instálalo manualmente desde:$\r$\n\
        https://www.docker.com/products/docker-desktop/$\r$\n\
        y luego abre POSVENDELO."
      ; No abortamos — los contenedores se levantarán cuando Docker esté listo
    ${EndIf}

    DetailPrint "Esperando que Docker Desktop inicie..."
    ; Darle hasta 90 segundos para que el daemon levante
    StrCpy $HEALTH_ATTEMPTS 0
    dockerWaitLoop:
      IntOp $HEALTH_ATTEMPTS $HEALTH_ATTEMPTS + 1
      ${If} $HEALTH_ATTEMPTS > 45
        Goto dockerReady
      ${EndIf}
      Sleep 2000
      nsExec::ExecToLog 'cmd /c docker info >nul 2>&1'
      Pop $0
      ${If} $0 == 0
        Goto dockerReady
      ${EndIf}
    Goto dockerWaitLoop
    dockerReady:
      DetailPrint "Docker Desktop listo."
  ${Else}
    DetailPrint "Docker Desktop ya instalado."
  ${EndIf}

  ; --------------------------------------------------------------------------
  ; 2. Crear directorio de datos
  ; --------------------------------------------------------------------------
  DetailPrint "Creando directorio de datos: $POS_DATA_DIR"
  CreateDirectory "$POS_DATA_DIR"
  CreateDirectory "$POS_DATA_DIR\backups"

  ; --------------------------------------------------------------------------
  ; 3. Generar .env (solo si no existe — nunca sobreescribir secretos)
  ; --------------------------------------------------------------------------
  ${If} ${FileExists} "$POS_ENV"
    DetailPrint ".env existente conservado."
  ${Else}
    DetailPrint "Generando .env con credenciales seguras..."
    ; Escribir script PS1 temporal para evitar escaping NSIS/PowerShell
    FileOpen $1 "$TEMP\posvendelo-genenv.ps1" w
    FileWrite $1 'param([string]$$envPath)$\r$\n'
    FileWrite $1 '$$jwtSecret = -join ((1..64) | ForEach-Object { "{0:x}" -f (Get-Random -Maximum 16) })$\r$\n'
    FileWrite $1 '$$dbPass = -join ((1..32) | ForEach-Object { [char](Get-Random -Minimum 65 -Maximum 123) })$\r$\n'
    FileWrite $1 '$$lines = @($\r$\n'
    FileWrite $1 '  "POSTGRES_PASSWORD=$$dbPass",$\r$\n'
    FileWrite $1 '  ("DATABASE_URL=postgresql+asyncpg://posvendelo_user:" + $$dbPass + "@postgres:5432/posvendelo"),$\r$\n'
    FileWrite $1 '  "JWT_SECRET=$$jwtSecret",$\r$\n'
    FileWrite $1 '  "ADMIN_API_USER=",$\r$\n'
    FileWrite $1 '  "ADMIN_API_PASSWORD=",$\r$\n'
    FileWrite $1 '  "DEBUG=false",$\r$\n'
    FileWrite $1 '  "BACKEND_IMAGE=ghcr.io/uriel2121ger-art/posvendelo:latest"$\r$\n'
    FileWrite $1 ')$\r$\n'
    FileWrite $1 '$$lines -join [Environment]::NewLine | Set-Content -Encoding UTF8 -Path $$envPath$\r$\n'
    FileClose $1
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -File "$TEMP\posvendelo-genenv.ps1" "$POS_ENV"'
    Pop $0
    ${If} $0 != 0
      DetailPrint "ADVERTENCIA: Fallo generación de .env via PowerShell. Usando fallback básico..."
      ; Fallback: escribir .env con placeholder (el wizard pedirá configuración)
      FileOpen $1 "$POS_ENV" w
      FileWrite $1 "POSTGRES_PASSWORD=changeme_on_first_run$\r$\n"
      FileWrite $1 "DATABASE_URL=postgresql+asyncpg://posvendelo_user:changeme_on_first_run@postgres:5432/posvendelo$\r$\n"
      FileWrite $1 "JWT_SECRET=changeme_jwt_secret_please_set_a_strong_value$\r$\n"
      FileWrite $1 "ADMIN_API_USER=$\r$\n"
      FileWrite $1 "ADMIN_API_PASSWORD=$\r$\n"
      FileWrite $1 "DEBUG=false$\r$\n"
      FileWrite $1 "BACKEND_IMAGE=ghcr.io/uriel2121ger-art/posvendelo:latest$\r$\n"
      FileClose $1
    ${EndIf}
    DetailPrint ".env generado."
  ${EndIf}

  ; --------------------------------------------------------------------------
  ; 4. Escribir docker-compose.yml (siempre — para recoger actualizaciones)
  ; --------------------------------------------------------------------------
  DetailPrint "Escribiendo docker-compose.yml..."
  FileOpen $1 "$POS_COMPOSE" w
  FileWrite $1 "services:$\r$\n"
  FileWrite $1 "  postgres:$\r$\n"
  FileWrite $1 "    image: postgres:15-alpine$\r$\n"
  FileWrite $1 "    environment:$\r$\n"
  FileWrite $1 "      POSTGRES_DB: posvendelo$\r$\n"
  FileWrite $1 "      POSTGRES_USER: posvendelo_user$\r$\n"
  FileWrite $1 "      POSTGRES_PASSWORD: $${POSTGRES_PASSWORD}$\r$\n"
  FileWrite $1 "    volumes:$\r$\n"
  FileWrite $1 "      - pgdata:/var/lib/postgresql/data$\r$\n"
  FileWrite $1 "    healthcheck:$\r$\n"
  FileWrite $1 '      test: ["CMD-SHELL", "pg_isready -U posvendelo_user -d posvendelo"]$\r$\n'
  FileWrite $1 "      interval: 10s$\r$\n"
  FileWrite $1 "      timeout: 5s$\r$\n"
  FileWrite $1 "      retries: 5$\r$\n"
  FileWrite $1 "    restart: unless-stopped$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "  api:$\r$\n"
  FileWrite $1 "    image: $${BACKEND_IMAGE}$\r$\n"
  FileWrite $1 "    env_file:$\r$\n"
  FileWrite $1 "      - .env$\r$\n"
  FileWrite $1 "    environment:$\r$\n"
  FileWrite $1 "      DATABASE_URL: $${DATABASE_URL}$\r$\n"
  FileWrite $1 "      JWT_SECRET: $${JWT_SECRET}$\r$\n"
  FileWrite $1 "      ADMIN_API_USER: $${ADMIN_API_USER:-}$\r$\n"
  FileWrite $1 "      ADMIN_API_PASSWORD: $${ADMIN_API_PASSWORD:-}$\r$\n"
  FileWrite $1 '      CORS_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"$\r$\n'
  FileWrite $1 '      CORS_ALLOWED_ORIGINS: "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"$\r$\n'
  FileWrite $1 "    ports:$\r$\n"
  FileWrite $1 '      - "127.0.0.1:8000:8000"$\r$\n'
  FileWrite $1 "    depends_on:$\r$\n"
  FileWrite $1 "      postgres:$\r$\n"
  FileWrite $1 "        condition: service_healthy$\r$\n"
  FileWrite $1 "    restart: unless-stopped$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "volumes:$\r$\n"
  FileWrite $1 "  pgdata:$\r$\n"
  FileClose $1
  DetailPrint "docker-compose.yml escrito."

  ; --------------------------------------------------------------------------
  ; 5. Pull de imagen e inicio de contenedores
  ; --------------------------------------------------------------------------
  DetailPrint "Descargando imagen del backend (puede tardar varios minutos la primera vez)..."
  nsExec::ExecToLog 'cmd /c cd /d "$POS_DATA_DIR" && docker compose pull'
  Pop $0
  ${If} $0 != 0
    DetailPrint "ADVERTENCIA: No se pudo descargar la imagen. El servicio iniciará cuando haya internet."
    Goto skipComposeUp
  ${EndIf}

  DetailPrint "Iniciando contenedores..."
  nsExec::ExecToLog 'cmd /c cd /d "$POS_DATA_DIR" && docker compose up -d'
  Pop $0
  ${If} $0 != 0
    DetailPrint "ADVERTENCIA: docker compose up falló. Revisa Docker Desktop."
    Goto skipComposeUp
  ${EndIf}
  DetailPrint "Contenedores iniciados."

  ; --------------------------------------------------------------------------
  ; 6. Esperar health endpoint (hasta 60 segundos)
  ; --------------------------------------------------------------------------
  DetailPrint "Esperando que el servidor esté listo..."
  StrCpy $HEALTH_ATTEMPTS 0
  healthLoop:
    IntOp $HEALTH_ATTEMPTS $HEALTH_ATTEMPTS + 1
    ${If} $HEALTH_ATTEMPTS > 30
      DetailPrint "El servidor tardó más de lo esperado. Abre POSVENDELO en unos minutos."
      Goto healthDone
    ${EndIf}
    Sleep 2000
    nsExec::ExecToLog \
      'cmd /c curl -sf http://127.0.0.1:8000/health >nul 2>&1'
    Pop $HEALTH_RESULT
    ${If} $HEALTH_RESULT == 0
      DetailPrint "¡Servidor listo en http://127.0.0.1:8000!"
      Goto healthDone
    ${EndIf}
  Goto healthLoop
  healthDone:

  skipComposeUp:

  ; --------------------------------------------------------------------------
  ; 7. Generar posvendelo-agent.json para auto-update
  ;    localAgent.ts busca en %LOCALAPPDATA%\POSVENDELO\
  ; --------------------------------------------------------------------------
  ; NSIS no tiene $LOCALAPPDATA built-in — leer de variable de entorno
  ReadEnvStr $POS_LOCAL_APPDATA LOCALAPPDATA
  StrCmp $POS_LOCAL_APPDATA "" 0 +2
    StrCpy $POS_LOCAL_APPDATA "$PROFILE\AppData\Local"
  StrCpy $POS_AGENT_DIR "$POS_LOCAL_APPDATA\POSVENDELO"
  StrCpy $POS_AGENT_FILE "$POS_AGENT_DIR\posvendelo-agent.json"

  ${IfNot} ${FileExists} "$POS_AGENT_FILE"
    DetailPrint "Generando posvendelo-agent.json..."
    CreateDirectory "$POS_AGENT_DIR"

    ; controlPlaneUrl default posvendelo.com — se sobreescribe via bootstrap si aplica
    FileOpen $1 "$POS_AGENT_FILE" w
    FileWrite $1 "{$\r$\n"
    FileWrite $1 '  "installDir": "'
    FileWrite $1 "$POS_DATA_DIR"
    FileWrite $1 '",$\r$\n'
    FileWrite $1 '  "controlPlaneUrl": "https://posvendelo.com",$\r$\n'
    FileWrite $1 '  "localApiUrl": "http://127.0.0.1:8000",$\r$\n'
    FileWrite $1 '  "backendHealthUrl": "http://127.0.0.1:8000/health",$\r$\n'
    FileWrite $1 '  "appArtifact": "electron-windows",$\r$\n'
    FileWrite $1 '  "backendArtifact": "backend",$\r$\n'
    FileWrite $1 '  "releaseChannel": "stable",$\r$\n'
    FileWrite $1 '  "pollIntervals": {$\r$\n'
    FileWrite $1 '    "healthSeconds": 30,$\r$\n'
    FileWrite $1 '    "manifestSeconds": 300,$\r$\n'
    FileWrite $1 '    "licenseSeconds": 3600$\r$\n'
    FileWrite $1 "  }$\r$\n"
    FileWrite $1 "}$\r$\n"
    FileClose $1
    DetailPrint "posvendelo-agent.json generado."
  ${Else}
    DetailPrint "posvendelo-agent.json existente conservado."
  ${EndIf}

  ; --------------------------------------------------------------------------
  ; 8. Escribir INSTALL_SUMMARY.txt
  ; --------------------------------------------------------------------------
  DetailPrint "Escribiendo resumen de instalación..."
  FileOpen $1 "$POS_SUMMARY" w
  FileWrite $1 "POSVENDELO - Instalado OK$\r$\n"
  FileWrite $1 "============================================$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "Abre la app POSVENDELO desde el menu Inicio$\r$\n"
  FileWrite $1 "o desde el acceso directo del escritorio.$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "Configura tu usuario al abrir el POS$\r$\n"
  FileWrite $1 "por primera vez.$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "Backend: http://127.0.0.1:8000$\r$\n"
  FileWrite $1 "Datos en: $POS_DATA_DIR$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "Para detener los servicios:$\r$\n"
  FileWrite $1 "  cd $POS_DATA_DIR$\r$\n"
  FileWrite $1 "  docker compose down$\r$\n"
  FileWrite $1 "$\r$\n"
  FileWrite $1 "Los datos de la base de datos se conservan en el$\r$\n"
  FileWrite $1 "volumen Docker 'posvendelo_pgdata'.$\r$\n"
  FileClose $1
  DetailPrint "¡Instalación completada! Abre POSVENDELO desde el menú Inicio."

!macroend


; =============================================================================
; customUnInstall — Detiene los contenedores al desinstalar la app Electron
; Los datos (volumen pgdata) se conservan intencionalmente.
; =============================================================================

!macro customUnInstall

  ; Re-leer PROGRAMDATA (las variables de customInstall no persisten en uninstall)
  ReadEnvStr $0 PROGRAMDATA
  StrCmp $0 "" 0 +2
    StrCpy $0 "C:\ProgramData"

  DetailPrint "Deteniendo servicios POSVENDELO..."
  nsExec::ExecToLog 'cmd /c cd /d "$0\POSVENDELO" && docker compose down'
  Pop $1
  ${If} $1 == 0
    DetailPrint "Contenedores detenidos."
  ${Else}
    DetailPrint "No se pudieron detener los contenedores (puede que Docker no esté corriendo)."
  ${EndIf}
  DetailPrint "Los datos en $0\POSVENDELO se conservan."
  DetailPrint "Elimínalos manualmente si no los necesitas."

!macroend
