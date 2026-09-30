#!/usr/bin/env bash
# Augustus Development Script (macOS / Linux)
# Runs both backend and frontend locally with one command. Ctrl+C stops both.
# This is the macOS/Linux sibling of dev.ps1.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# --- colors ---
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; GRAY='\033[0;90m'; NC='\033[0m'
info()  { printf "${YELLOW}[INFO]${NC} %s\n" "$1"; }
ok()    { printf "${GREEN}[OK]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
err()   { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

printf "\n${CYAN}  =======================================${NC}\n"
printf "${CYAN}         AUGUSTUS - Development Mode${NC}\n"
printf "${CYAN}         Audio Intelligence Platform${NC}\n"
printf "${CYAN}  =======================================${NC}\n\n"

# --- prerequisite checks ---
# Backend requires Python 3.10+ (the `mcp` dep and Dockerfile use 3.11).
# Probe versioned interpreters first, then fall back to `python3` if it qualifies.
PYTHON_BIN=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  p="$(command -v "$cand" 2>/dev/null)" || continue
  if "$p" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
    PYTHON_BIN="$p"; break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  err "No Python 3.10+ found (backend needs 3.11). Detected: $(python3 --version 2>&1 || echo none)."
  err "Install one, then re-run ./dev.sh. Options:"
  err "  • Homebrew:  brew install python@3.11"
  err "  • Installer: https://www.python.org/downloads/  (get 3.11 or 3.12)"
  exit 1
fi
ok "Python found: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
command -v node >/dev/null 2>&1 || { err "Node.js not found. Install Node 18+ (brew install node)"; exit 1; }
ok "Node.js found: $(command -v node)"
command -v npm  >/dev/null 2>&1 || { err "npm not found. Install Node 18+"; exit 1; }

# --- .env: create template if missing, then export into this process ---
ENV_FILE="$ROOT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  warn "No .env file found. Creating template..."
  cat > "$ENV_FILE" <<'EOF'
# Augustus Configuration
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
TTS_PROVIDER=piper
ELEVENLABS_API_KEY=
DEBUG=true
EOF
  info "Created .env — add your OPENROUTER_API_KEY to use LLM features."
fi
# Export each KEY=value line, stripping a leading UTF-8 BOM and skipping comments/blanks.
while IFS= read -r line || [ -n "$line" ]; do
  line="${line#$'\xEF\xBB\xBF'}"           # strip BOM if present on first line
  case "$line" in ''|\#*) continue;; esac  # skip blanks and comments
  [[ "$line" == *=* ]] && export "$line"
done < "$ENV_FILE"

# --- free stale ports from previous runs ---
for port in 8000 3000; do
  pids="$(lsof -ti "tcp:$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    info "Killing stale process(es) on port $port: $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
  fi
done
sleep 1

# --- ensure runtime dirs exist ---
mkdir -p "$ROOT_DIR/audio" "$ROOT_DIR/models" "$ROOT_DIR/data"

# --- backend venv + deps ---
VENV_DIR="$ROOT_DIR/backend/venv"
VENV_PY="$VENV_DIR/bin/python"
if [ ! -x "$VENV_PY" ]; then
  info "Creating Python virtual environment..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  info "Installing backend dependencies (first run)..."
  "$VENV_DIR/bin/pip" install --upgrade pip -q
  "$VENV_DIR/bin/pip" install -r "$ROOT_DIR/backend/requirements.txt"
fi
ok "Backend environment ready"

# --- frontend deps ---
if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  info "Installing frontend dependencies (first run)..."
  (cd "$ROOT_DIR/frontend" && npm install)
fi
ok "Frontend dependencies ready"

# --- local IP for network access ---
LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"

printf "\n${GREEN}========================================${NC}\n"
printf "${GREEN}  Starting Augustus Services...${NC}\n"
printf "${GREEN}========================================${NC}\n\n"
printf "${CYAN}   Local Access:${NC}\n"
printf "   Frontend: http://localhost:3000\n"
printf "   Backend:  http://localhost:8000\n"
printf "   API Docs: http://localhost:8000/docs\n"
if [ -n "$LOCAL_IP" ]; then
  printf "\n${CYAN}   Network Access (other devices):${NC}\n"
  printf "   Frontend: http://%s:3000\n" "$LOCAL_IP"
fi
printf "\n${GRAY}   Press Ctrl+C to stop all services${NC}\n\n"

# --- start services ---
BACKEND_PID=""; FRONTEND_PID=""
cleanup() {
  printf "\n"; info "Shutting down Augustus..."
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null || true
  # safety net: free the ports (uvicorn --reload / vite spawn children)
  for port in 8000 3000; do
    pids="$(lsof -ti "tcp:$port" 2>/dev/null || true)"
    # shellcheck disable=SC2086
    [ -n "$pids" ] && kill $pids 2>/dev/null || true
  done
  ok "Augustus stopped."
}
trap cleanup EXIT INT TERM

# Backend (uvicorn with hot reload)
( cd "$ROOT_DIR/backend" && exec "$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload ) &
BACKEND_PID=$!
ok "Backend started (PID: $BACKEND_PID)"

# Wait for backend port to listen (max 60s)
info "Waiting for backend to be ready..."
for i in $(seq 1 60); do
  if lsof -ti "tcp:8000" >/dev/null 2>&1; then ok "Backend is ready! (took ${i}s)"; break; fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then err "Backend exited unexpectedly"; exit 1; fi
  sleep 1
  [ "$i" -eq 60 ] && warn "Backend not ready after 60s, starting frontend anyway..."
done

# Frontend (vite)
( cd "$ROOT_DIR/frontend" && exec npm run dev ) &
FRONTEND_PID=$!
ok "Frontend started (PID: $FRONTEND_PID)"

printf "\n${GREEN}[OK] Services running! Open http://localhost:3000${NC}\n\n"

# Wait until either service exits, then cleanup runs via trap.
# (poll loop instead of `wait -n` so it works on macOS's default bash 3.2)
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 2
done
