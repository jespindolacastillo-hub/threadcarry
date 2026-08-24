#!/bin/bash
# install.sh — threadcarry en 1 línea
# ============================================================================
# Instala threadcarry en tu workspace: copia el script, crea .continuity/,
# y opcionalmente configura hooks para Claude Code (capture en cada turno).
#
# Uso:
#   bash install.sh                       # instala en el workspace actual
#   bash install.sh /ruta/al/workspace    # instala en otro workspace
#   CONTINUITY_WORKSPACE=/x bash install.sh
#
# El estado viaja con tu workspace por Dropbox/Drive/Syncthing/git — cualquier
# carpeta sincronizada que ya uses. Cero infraestructura.

set -euo pipefail

# ── determinar workspace ──────────────────────────────────────────────────────
if [[ -n "${CONTINUITY_WORKSPACE:-}" ]]; then
  WS="$CONTINUITY_WORKSPACE"
elif [[ -n "${1:-}" ]]; then
  WS="$1"
else
  WS="$(pwd)"
fi
WS="$(cd "$WS" 2>/dev/null && pwd || echo "$WS")"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$WS/.continuity"

echo "🧵 threadcarry — instalando en: $WS"

# ── copiar el script ─────────────────────────────────────────────────────────
mkdir -p "$DEST"
if [[ -f "$SCRIPT_DIR/continuity.py" ]]; then
  cp "$SCRIPT_DIR/continuity.py" "$DEST/continuity.py"
else
  echo "❌ no encuentro continuity.py junto a install.sh"
  exit 1
fi
chmod +x "$DEST/continuity.py"
echo "✅ script copiado a $DEST/continuity.py"

# ── captura inicial del estado ────────────────────────────────────────────────
(cd "$WS" && python3 "$DEST/continuity.py" capture) 2>/dev/null || true

# ── hooks de Claude Code (opcional, pregunta) ─────────────────────────────────
CLAUDE_SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
if [[ -f "$CLAUDE_SETTINGS" ]] && command -v jq >/dev/null 2>&1; then
  read -r -p "¿Configurar hooks automáticos para Claude Code? (y/N) " yn
  if [[ "$yn" == "y" || "$yn" == "Y" ]]; then
    python3 - "$CLAUDE_SETTINGS" "$WS" <<'PYEOF'
import json, sys, os
path, ws = sys.argv[1], sys.argv[2]
data = json.load(open(path)) if os.path.exists(path) else {}
hooks = data.setdefault("hooks", {})
capture = f'python3 "{ws}/.continuity/continuity.py" capture 2>&1 || true'
# SessionStart: registrar inicio de sesión (también imprime resume)
ss = hooks.setdefault("SessionStart", [{"matcher": "", "hooks": []}])
ss[0]["hooks"].append({"type": "command",
  "command": f'python3 "{ws}/.continuity/continuity.py" resume 2>&1 || true'})
# Stop: capturar estado al cerrar
st = hooks.setdefault("Stop", [{"matcher": "", "hooks": []}])
st[0]["hooks"].append({"type": "command", "command": capture})
json.dump(data, open(path, "w"), indent=2)
print(f"✅ hooks agregados a {path}")
PYEOF
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ threadcarry instalado. Pruébalo:"
echo ""
echo "  python3 .continuity/continuity.py resume    # ¿dónde quedé?"
echo "  python3 .continuity/continuity.py whatdid   # ¿qué hice ayer?"
echo ""
echo "  Multi-máquina: pon tu workspace en una carpeta"
echo "  sincronizada (Dropbox/Drive/Syncthing) y listo."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
