#!/usr/bin/env bash
# =============================================================================
#  start.sh  —  Cyber-Intel AI Agent  |  One-command launcher
# =============================================================================
#
#  What this does (fully automated):
#    1. Kills any stale process on MCP_PORT
#    2. Starts server.py in the background
#    3. Downloads cloudflared if not already present
#    4. Opens a Cloudflare Quick Tunnel and captures the public URL
#    5. Writes the URL to .env  (MCP_SERVER_URL)
#    6. Prints the command to run agent.py
#    7. Keeps server + tunnel alive until Ctrl+C
#
#  Usage:
#    bash start.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Load .env for MCP_PORT / MCP_HOST ───────────────────────────────────────
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# ── Config ────────────────────────────────────────────────────────────────────
PORT="${MCP_PORT:-8000}"
CLOUDFLARED="/tmp/cloudflared"
TUNNEL_LOG="/tmp/cyberintel_tunnel.log"
VENV_PYTHON=".venv/bin/python"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m';   CYAN='\033[0;36m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
err()  { echo -e "${RED}[✗]${RESET} $*"; }
info() { echo -e "${CYAN}[→]${RESET} $*"; }

# ── Trap: guaranteed cleanup on exit / Ctrl+C ─────────────────────────────────
SERVER_PID=""
TUNNEL_PID=""
cleanup() {
    echo ""
    info "Shutting down..."
    [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null \
        && ok "MCP server stopped  (was PID $SERVER_PID)"
    [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null \
        && ok "Tunnel closed       (was PID $TUNNEL_PID)"
    echo ""
}
trap cleanup EXIT INT TERM

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "   Cyber-Intel AI Agent  —  Startup"
echo "══════════════════════════════════════════════════"
echo ""

# ── Guard: venv must exist ────────────────────────────────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
    err "Virtual environment not found."
    err "Run:  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# ── Guard: .env must exist ────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    err ".env not found. Copy .env.template → .env and fill in your Azure values."
    exit 1
fi

# ── Step 1: Clear stale port ──────────────────────────────────────────────────
info "Step 1/4 — Clearing port $PORT..."
if fuser "${PORT}/tcp" > /dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null; sleep 1
    ok "Stale process on :$PORT killed"
else
    ok "Port $PORT is free"
fi
pkill -f "cloudflared tunnel" 2>/dev/null && warn "Stale tunnel process killed" || true
sleep 0.5

# ── Step 2: Start MCP server ──────────────────────────────────────────────────
info "Step 2/4 — Starting CyberIntel MCP server..."
"$VENV_PYTHON" server.py &
SERVER_PID=$!
sleep 2

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    err "MCP server failed to start. Check server.py for errors."
    exit 1
fi
ok "MCP server running  (PID $SERVER_PID, port $PORT)"

# Verify the streamable-http MCP endpoint is listening
if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/mcp" 2>/dev/null \
    || curl -sf -o /dev/null -X POST "http://127.0.0.1:${PORT}/mcp" 2>/dev/null; then
    ok "MCP endpoint reachable at http://127.0.0.1:${PORT}/mcp"
else
    warn "MCP endpoint not yet responding — server process is up, continuing..."
fi

# ── Step 3: Download cloudflared if needed ────────────────────────────────────
info "Step 3/4 — Preparing Cloudflare tunnel..."
if [ ! -f "$CLOUDFLARED" ]; then
    info "Downloading cloudflared binary..."
    wget -q \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" \
        -O "$CLOUDFLARED"
    chmod +x "$CLOUDFLARED"
    ok "cloudflared downloaded"
else
    ok "cloudflared already present ($CLOUDFLARED)"
fi

# ── Step 4: Start tunnel and capture URL ──────────────────────────────────────
info "Step 4/4 — Opening Cloudflare Quick Tunnel (this can take ~10 s)..."
rm -f "$TUNNEL_LOG"
"$CLOUDFLARED" tunnel --url "http://localhost:$PORT" --no-autoupdate \
    > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

TUNNEL_URL=""
for i in $(seq 1 40); do
    # Exit early if cloudflared crashed
    if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
        err "cloudflared exited unexpectedly."
        err "Last log:"
        tail -10 "$TUNNEL_LOG" >&2
        exit 1
    fi
    TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' \
        "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    [ -n "$TUNNEL_URL" ] && break
    sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
    err "Tunnel URL not received within 40 seconds."
    err "Full log at: $TUNNEL_LOG"
    exit 1
fi

ok "Tunnel active: ${CYAN}${TUNNEL_URL}${RESET}"

# ── Update .env ───────────────────────────────────────────────────────────────
sed -i "s|MCP_SERVER_URL=.*|MCP_SERVER_URL=${TUNNEL_URL}/mcp|" .env
ok ".env updated  →  MCP_SERVER_URL=${TUNNEL_URL}/mcp"

# ── Ready ─────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo -e "  ${GREEN}All systems ready.${RESET}"
echo ""
echo -e "  Open a ${YELLOW}NEW terminal tab${RESET} and run:"
echo ""
echo -e "    ${CYAN}cd $SCRIPT_DIR && .venv/bin/python agent.py${RESET}"
echo ""
echo "  Keep THIS window open. Ctrl+C stops everything."
echo "══════════════════════════════════════════════════"
echo ""

# Block until MCP server exits (then cleanup fires via trap)
wait "$SERVER_PID" 2>/dev/null || true
