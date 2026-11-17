#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/.logs"
PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"

BACKEND_PORT="${BACKEND_PORT:-5000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
ADMIN_EMAIL="${ADMIN_EMAIL:-usuario@example.invalid}"
ADMIN_NAME="${ADMIN_NAME:-Administrador}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-REEMPLAZAR_SECRETO_LOCAL}"

USE_SQLITE=0
SKIP_INSTALL=0
SKIP_ADMIN=0
KILL_PORTS=0
PIDS=()
CLEANED_UP=0

usage() {
  cat <<USAGE
Uso:
  ./scripts/levantar_pruebas.sh [opciones]

Opciones:
  --sqlite        Usa SQLite local en almacenamiento/calidad_web_dev.db y no requiere PostgreSQL.
  --skip-install Omite instalacion/verificacion de dependencias.
  --skip-admin   No crea el usuario administrador de prueba.
  --kill-ports   Libera los puertos BACKEND_PORT y FRONTEND_PORT antes de arrancar.
  -h, --help     Muestra esta ayuda.

Variables utiles:
  BACKEND_PORT=5000 FRONTEND_PORT=5173 ADMIN_EMAIL=usuario@example.invalid ADMIN_PASSWORD=REEMPLAZAR_SECRETO_LOCAL
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sqlite)
      USE_SQLITE=1
      shift
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --skip-admin)
      SKIP_ADMIN=1
      shift
      ;;
    --kill-ports)
      KILL_PORTS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Opcion no reconocida: $1"
      usage
      exit 1
      ;;
  esac
done

cleanup() {
  if [[ "$CLEANED_UP" -eq 1 ]]; then
    return
  fi
  CLEANED_UP=1
  echo
  echo "Apagando procesos locales..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -- "-$pid" >/dev/null 2>&1 || kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

run_npm() {
  if command -v npm >/dev/null 2>&1; then
    npm "$@"
  elif command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c npm "$@"
  else
    echo "No encontre npm. Instala Node.js y npm antes de levantar el frontend."
    exit 1
  fi
}

port_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser "$port/tcp" 2>/dev/null || true
  fi
  if command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c "netstat -ano | findstr :$port" 2>/dev/null | awk '/LISTENING/ {print $NF}' | tr -d '\r' || true
  fi
}

prepare_port() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(port_pids "$port")"
  if [[ -z "$pids" ]]; then
    return
  fi

  if [[ "$KILL_PORTS" -eq 1 ]]; then
    echo "Liberando puerto $port para $label..."
    for pid in $pids; do
      kill "$pid" >/dev/null 2>&1 || true
      if command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c "taskkill /PID $pid /F" >/dev/null 2>&1 || true
      fi
    done
    sleep 1
    return
  fi

  echo "El puerto $port ($label) ya esta en uso por: $pids"
  echo "Cierra ese proceso o ejecuta: ./scripts/levantar_pruebas.sh --kill-ports"
  exit 1
}

ensure_backend_env() {
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Creando entorno virtual del backend..."
    python3 -m venv "$BACKEND_DIR/.venv"
  fi

  if [[ "$SKIP_INSTALL" -eq 0 ]]; then
    if ! "$PYTHON_BIN" -c "import flask, flask_migrate, flask_sqlalchemy, flask_jwt_extended" >/dev/null 2>&1; then
      echo "Instalando dependencias del backend..."
      "$PYTHON_BIN" -m pip install -r "$BACKEND_DIR/requirements.txt"
    fi
  fi
}

ensure_frontend_env() {
  if [[ "$SKIP_INSTALL" -eq 1 ]]; then
    return
  fi
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Instalando dependencias del frontend..."
    (cd "$FRONTEND_DIR" && run_npm install)
  fi
}

configure_runtime_env() {
  export ENTORNO_APLICACION="${ENTORNO_APLICACION:-desarrollo}"
  export CLAVE_SESION="${CLAVE_SESION:-clave-local-desarrollo-cambiala}"
  export CLAVE_JWT="${CLAVE_JWT:-clave-jwt-local-desarrollo-cambiala}"
  export CLAVE_CIFRADO_SECRETOS="${CLAVE_CIFRADO_SECRETOS:-clave-local-de-cifrado-minimo-32-bytes}"
  export ORIGEN_FRONTEND_PERMITIDO="http://localhost:$FRONTEND_PORT"
  export URL_PUBLICA_BACKEND="http://localhost:$BACKEND_PORT"
  export URL_PUBLICA_FRONTEND="http://localhost:$FRONTEND_PORT"
  export RUTA_EVIDENCIAS="${RUTA_EVIDENCIAS:-$ROOT_DIR/almacenamiento/evidencias}"

  if [[ "$USE_SQLITE" -eq 1 ]]; then
    export CADENA_CONEXION_POSTGRESQL="sqlite:///$ROOT_DIR/almacenamiento/calidad_web_dev.db"
  fi
}

upgrade_database() {
  echo "Aplicando migraciones..."
  (cd "$BACKEND_DIR" && "$PYTHON_BIN" -m flask --app wsgi db upgrade)
}

ensure_admin() {
  if [[ "$SKIP_ADMIN" -eq 1 ]]; then
    return
  fi

  echo "Verificando administrador de prueba..."
  (cd "$BACKEND_DIR" && "$PYTHON_BIN" - <<PY
from werkzeug.security import generate_password_hash

from aplicacion import crear_aplicacion
from aplicacion.extensiones import db
from aplicacion.modelos import Rol, Usuario

correo = "${ADMIN_EMAIL}".lower()
nombre = "${ADMIN_NAME}"
contrasena = "${ADMIN_PASSWORD}"

app = crear_aplicacion()
with app.app_context():
    rol = Rol.query.filter_by(nombre="administrador").first()
    if rol is None:
        rol = Rol(nombre="administrador", descripcion="Gestion completa de la plataforma")
        db.session.add(rol)
    usuario = Usuario.query.filter_by(correo=correo).first()
    if usuario is None:
        usuario = Usuario(
            nombre=nombre,
            correo=correo,
            contrasena_hash=generate_password_hash(contrasena),
            activo=True,
            roles=[rol],
        )
        db.session.add(usuario)
        db.session.commit()
        print(f"Administrador creado: {correo}")
    else:
        print(f"Administrador existente: {correo}")
PY
  )
}

start_processes() {
  mkdir -p "$LOG_DIR"
  : > "$LOG_DIR/backend.log"
  : > "$LOG_DIR/trabajador.log"
  : > "$LOG_DIR/programador.log"
  : > "$LOG_DIR/frontend.log"

  echo "Arrancando backend en http://localhost:$BACKEND_PORT ..."
  start_logged "$BACKEND_DIR" "$LOG_DIR/backend.log" "$PYTHON_BIN" -m flask --app wsgi run --host 127.0.0.1 --port "$BACKEND_PORT"

  echo "Arrancando trabajador..."
  start_logged "$BACKEND_DIR" "$LOG_DIR/trabajador.log" "$PYTHON_BIN" trabajador.py

  echo "Arrancando programador..."
  start_logged "$BACKEND_DIR" "$LOG_DIR/programador.log" "$PYTHON_BIN" programador.py

  echo "Arrancando frontend en http://localhost:$FRONTEND_PORT ..."
  if command -v npm >/dev/null 2>&1; then
    start_logged "$FRONTEND_DIR" "$LOG_DIR/frontend.log" npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
  elif command -v cmd.exe >/dev/null 2>&1; then
    start_logged "$FRONTEND_DIR" "$LOG_DIR/frontend.log" cmd.exe /c npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
  else
    echo "No encontre npm. Instala Node.js y npm antes de levantar el frontend."
    exit 1
  fi
}

start_logged() {
  local workdir="$1"
  local logfile="$2"
  shift 2
  setsid bash -c 'cd "$1" || exit 1; shift; exec "$@"' _ "$workdir" "$@" >"$logfile" 2>&1 &
  PIDS+=("$!")
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local tries=40

  for _ in $(seq 1 "$tries"); do
    if command -v curl >/dev/null 2>&1 && curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name disponible: $url"
      return
    fi
    if command -v cmd.exe >/dev/null 2>&1 && cmd.exe /c "curl -fsS $url" >/dev/null 2>&1; then
      echo "$name disponible: $url"
      return
    fi
    sleep 0.5
  done
  echo "No pude confirmar $name en $url. Revisa los logs en $LOG_DIR."
}

main() {
  cd "$ROOT_DIR"
  configure_runtime_env
  ensure_backend_env
  ensure_frontend_env
  upgrade_database
  ensure_admin
  prepare_port "$BACKEND_PORT" "backend"
  prepare_port "$FRONTEND_PORT" "frontend"
  start_processes

  wait_for_url "Backend" "http://127.0.0.1:$BACKEND_PORT/api/salud"
  wait_for_url "Frontend" "http://127.0.0.1:$FRONTEND_PORT"

  echo
  echo "Listo para probar:"
  echo "  Frontend: http://localhost:$FRONTEND_PORT"
  echo "  Backend:  http://localhost:$BACKEND_PORT"
  echo "  Usuario:  $ADMIN_EMAIL"
  if [[ "$SKIP_ADMIN" -eq 0 ]]; then
    echo "  Clave:    $ADMIN_PASSWORD"
  fi
  echo
  echo "Logs en vivo. Presiona Ctrl+C para apagar todo."
  tail -n +1 -f "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log" "$LOG_DIR/trabajador.log" "$LOG_DIR/programador.log"
}

main
