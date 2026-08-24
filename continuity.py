#!/usr/bin/env python3
"""
continuity.py — Estado vivo de sesión + resume entre máquinas
================================================================
La pieza que cierra el círculo de la continuidad multi-máquina:

  capture   → escribe .continuity/state.json (se actualiza en cada turno
              vía hooks, sin esperar al cierre de sesión)
  resume    → imprime el resumen de la última sesión registrada, para que
              CUALQUIER agente (Claude Code, Gemini, Codex, DSH...) lo lea
              al iniciar y sepa exactamente dónde se quedó — en cualquier
              máquina, porque el estado viaja con el workspace.

Diseñado SIN dependencias del resto del framework y sin paths hardcodeados:
portable a cualquier workspace (ver CONTINUITY_WORKSPACE / --workspace).

Uso:
  python3 continuity.py capture                 # hooks: UserPromptSubmit/Stop
  python3 continuity.py resume                  # inicio de sesión: ¿dónde quedé?
  python3 continuity.py status                  # estado crudo (debug)
  python3 continuity.py capture --workspace X   # workspace alternativo

El archivo de estado vive en <workspace>/.continuity/state.json
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_WORKSPACE = Path(os.environ.get("HOME", ".")) / "workspace"  # configurable: CONTINUITY_WORKSPACE
NOISE = ("PROJECT_STATUS.md", ".DS_Store", "supabase/.temp/",
         "package-lock.json", ".claude/active-sessions.json")
STALE_SECONDS = 24 * 3600  # una sesión "vieja" = sin actividad en 24h


# ── Helpers ───────────────────────────────────────────────────────────────────

def workspace_dir() -> Path:
    ws = os.environ.get("CONTINUITY_WORKSPACE")
    return Path(ws) if ws else DEFAULT_WORKSPACE


def state_path(ws: Path) -> Path:
    return ws / ".continuity" / "state.json"


def _load_state(ws: Path):
    """Carga el estado guardado (dict) o None si no existe/corrupto."""
    sp = state_path(ws)
    if not sp.exists():
        return None
    try:
        return json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return None


def git(repo: Path, *args, timeout=8):
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception:
        return "", -1


def find_git_root(start: Path):
    """Busca el repo git más cercano subiendo desde el cwd."""
    cur = start.resolve()
    for _ in range(6):
        if (cur / ".git").exists() or (cur / ".git").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def git_status_files(repo: Path, max_files=8):
    out, _ = git(repo, "status", "--porcelain")
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if any(n in path for n in NOISE):
            continue
        files.append(path)
    return files[:max_files]


def git_last_commits(repo: Path, max_commits=5):
    out, _ = git(repo, "log", "-%d" % max_commits,
                 "--format=%h %s", "--no-merges")
    return [l for l in out.splitlines() if l.strip()][:max_commits]


def read_wip_in_progress(ws: Path):
    """Extrae la tarea en progreso del WORK_IN_PROGRESS.md (si existe)."""
    wip = ws / "WORK_IN_PROGRESS.md"
    if not wip.exists():
        return None
    try:
        content = wip.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    start = content.find("## 🔄 Tarea en progreso")
    if start == -1:
        return None
    end = content.find("\n## ", start + 1)
    section = content[start:end if end != -1 else None]
    data = {}
    for line in section.splitlines():
        for field in ["Proyecto", "Objetivo", "Estado"]:
            key = f"**{field}:**"
            if key in line:
                value = line.split(key)[-1].strip()
                if value and "/" not in value:  # saltar placeholders
                    data[field.lower()] = value
    estado = data.get("estado", "")
    if estado.upper() in ("INICIADO", "EN PROGRESO") and data.get("objetivo"):
        return {"proyecto": data.get("proyecto", ""), "objetivo": data["objetivo"]}
    return None


def relative_time(ts_epoch: float) -> str:
    now = time.time()
    diff = now - ts_epoch
    if diff < 60:
        return "hace <1 min"
    if diff < 3600:
        return f"hace {int(diff / 60)} min"
    if diff < 86400:
        return f"hace {int(diff / 3600)} h"
    return f"hace {int(diff / 86400)} días"


# ── capture ───────────────────────────────────────────────────────────────────

def capture(ws: Path) -> dict:
    """Escribe el estado vivo de la sesión actual."""
    cwd = Path.cwd()
    git_root = find_git_root(cwd)
    repo_name = git_root.name if git_root else None

    state = {
        "version": 1,
        "lastMachine": socket.gethostname(),
        "lastActivityEpoch": int(time.time()),
        "lastActivityIso": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "project": repo_name,
        "branch": None,
        "uncommitted": [],
        "lastActions": [],
        "wipTask": None,
        "cwd": str(cwd),
    }
    if git_root:
        state["branch"], _ = git(git_root, "branch", "--show-current")
        state["uncommitted"] = git_status_files(git_root)
        state["lastActions"] = git_last_commits(git_root)
    state["wipTask"] = read_wip_in_progress(ws)

    sp = state_path(ws)
    sp.parent.mkdir(parents=True, exist_ok=True)
    tmp = sp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, sp)  # atómico: nunca deja un archivo a medio escribir
    return state


# ── resume ────────────────────────────────────────────────────────────────────

def format_resume(state: dict, current_machine: str) -> str:
    """Convierte el estado en el mensaje que lee el agente (el momento WOW)."""
    if not state:
        return "🆕 Sin sesión previa registrada — este es el primer arranque con continuidad."
    lines = []
    machine = state.get("lastMachine", "?")
    ts = state.get("lastActivityEpoch", 0)
    same_machine = machine == current_machine

    if not same_machine:
        lines.append(f"⏭️  Sesión anterior: **{machine}** · {relative_time(ts)}")
        lines.append("   🌍 Estás en OTRA máquina — esto viajó contigo desde el workspace.")
    else:
        lines.append(f"⏭️  Última sesión en esta máquina: {relative_time(ts)}")

    project = state.get("project")
    branch = state.get("branch")
    if project:
        branch_note = f" · rama `{branch}`" if branch else ""
        lines.append(f"📁 Proyecto: {project}{branch_note}")

    wip = state.get("wipTask")
    if wip:
        lines.append(f"🔧 En progreso: {wip['objetivo'][:100]}")
        if wip.get("proyecto"):
            lines.append(f"   (proyecto: {wip['proyecto']})")

    uncommitted = state.get("uncommitted") or []
    if uncommitted:
        sample = ", ".join(uncommitted[:4])
        more = f" … y {len(uncommitted) - 4} más" if len(uncommitted) > 4 else ""
        lines.append(f"⚠️ {len(uncommitted)} archivo(s) sin commitear: {sample}{more}")

    actions = state.get("lastActions") or []
    if actions:
        lines.append(f"🔄 Últimas acciones: {' · '.join(actions[:3])}")

    lines.append("")
    lines.append("¿Continúo donde estabas? (si la sesión quedó cortada, el estado de arriba es el punto exacto de retoma)")
    return "\n".join(lines)


def resume(ws: Path) -> int:
    sp = state_path(ws)
    if not sp.exists():
        print(format_resume(None, socket.gethostname()))
        return 0
    try:
        state = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        print("⚠️ estado de continuidad corrupto — correr `continuity.py capture` para regenerarlo")
        return 1
    print(format_resume(state, socket.gethostname()))
    return 0


# ── status (debug) ────────────────────────────────────────────────────────────

def status(ws: Path) -> int:
    sp = state_path(ws)
    if not sp.exists():
        print(f"no hay estado en {sp}")
        return 1
    print(sp.read_text(encoding="utf-8"))
    return 0


# ── whatdid: "¿qué hice ayer?" (el producto) ──────────────────────────────────

def _git(repo: Path, *args, timeout=8):
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _git_status_raw(repo: Path, timeout=8):
    """git status --porcelain SIN strip global: cada línea empieza con un
    espacio (' M archivo'), y un .strip() global se come ese espacio, lo que
    corre el slice [3:] un carácter (bug real: 'index.html' → 'ndex.html')."""
    try:
        r = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.splitlines()
    except Exception:
        return []


def whatdid(ws: Path, days: int) -> int:
    """Responde '¿qué hice en los últimos N días?' cruzando todos los repos
    del workspace: commits + cambios sin commitear + tarea en progreso."""
    today = datetime.now().strftime("%A %d de %B, %Y")
    print(f"📅 Lo que hiciste en los últimos {days} día(s) — hoy {today}")
    print("=" * 62)

    repos = []
    r = subprocess.run(["find", str(ws), "-maxdepth", "3", "-name", ".git", "-type", "d"],
                       capture_output=True, text=True, timeout=30)
    for line in r.stdout.strip().splitlines():
        repos.append(Path(line.replace("/.git", "")))

    # nombres amigables conocidos — leídos de .continuity/friendly-names.json
    # (config opcional del usuario; el script es genérico sin esto)
    friendly = {}
    fn_file = ws / ".continuity" / "friendly-names.json"
    if fn_file.exists():
        try:
            friendly = json.loads(fn_file.read_text(encoding="utf-8"))
        except Exception:
            friendly = {}
    noise = ("PROJECT_STATUS.md", ".DS_Store", "supabase/.temp/", "package-lock.json")

    active = []
    for repo in sorted(repos):
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00")
        out = _git(repo, "log", "--since=" + since, "--format=%s", "--no-merges")
        commits = [c.strip() for c in out.splitlines() if c.strip()]
        out2 = _git_status_raw(repo)
        uncommitted = []
        for line in out2:
            if not line.strip():
                continue
            p = line[3:].strip()
            if not any(n in p for n in noise):
                uncommitted.append(p)
        if commits or uncommitted:
            name = friendly.get(repo.name, repo.name)
            active.append((name, commits, uncommitted[:6], repo))

    if not active:
        print("   (sin actividad registrada en este período)")
        return 0

    # 1) proyectos con commits
    with_commits = [a for a in active if a[1]]
    if with_commits:
        print("\n✅ PROYECTOS DONDE TRABAJASTE:")
        for name, commits, uncommitted, repo in sorted(with_commits, key=lambda a: -len(a[1])):
            print(f"\n  📁 {name} — {len(commits)} commit(s):")
            for c in commits[:6]:
                print(f"     • {c[:95]}")
            if len(commits) > 6:
                print(f"     … +{len(commits) - 6} más")

    # 2) trabajo sin commitear (puede venir de otra máquina)
    pending = [(name, u, repo) for name, c, u, repo in active if u]
    if pending:
        print("\n⚠️ QUEDÓ SIN COMMITEAR (revisar — puede ser de otra máquina):")
        for name, uncommitted, repo in pending:
            sample = ", ".join(uncommitted[:4])
            more = f" … y {len(uncommitted) - 4} más" if len(uncommitted) > 4 else ""
            print(f"  • {name}: {len(uncommitted)} archivo(s) — {sample}{more}")

    # 3) tarea en progreso del WIP
    wip = read_wip_in_progress(ws)
    if wip:
        print(f"\n🔧 EN PROGRESO AHORA: {wip['objetivo'][:100]}")
        if wip.get("proyecto"):
            print(f"   (proyecto: {wip['proyecto']})")

    # 4) el resume de la última sesión (dónde quedaste)
    state = _load_state(ws)
    if state:
        print("\n⏭️ DÓNDE QUEDÓ LA ÚLTIMA SESIÓN:")
        print(format_resume(state, socket.gethostname()))

    print("\n" + "=" * 62)
    print("💡 Correr `continuity.py whatdid` cada mañana = tu memoria de trabajo.")
    return 0


# ── agentlog: bitácora del agente (qué pedí vs qué hizo) ─────────────────────

def _agent_log_path(ws: Path) -> Path:
    return ws / ".continuity" / "agent-log.json"


def _load_agent_log(ws: Path) -> list:
    p = _agent_log_path(ws)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_agent_log(ws: Path, entries: list):
    p = _agent_log_path(ws)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _changed_files_since(repo: Path, since_epoch: float, max_files=15):
    """Archivos modificados en el repo desde un timestamp (sin commits — working tree)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only", "--no-renames",
             "--since=" + datetime.fromtimestamp(since_epoch).strftime("%Y-%m-%d %H:%M:%S")],
            capture_output=True, text=True, timeout=10)
        files = [f for f in r.stdout.splitlines() if f.strip()][:max_files]
    except Exception:
        files = []
    # + untracked
    try:
        r2 = subprocess.run(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"],
                            capture_output=True, text=True, timeout=10)
        files += [f for f in r2.stdout.splitlines() if f.strip()][:max_files]
    except Exception:
        pass
    return list(dict.fromkeys(files))  # dedup manteniendo orden


def agentlog(ws: Path, prompt: str, cmd: str) -> int:
    """Registra un turno de trabajo del agente en la bitácora.

    Uso:
      continuity.py agentlog --prompt "arregla X"      # al empezar turno
      continuity.py agentlog --diff                     # al terminar turno (registra qué cambió)
    """
    log = _load_agent_log(ws)
    git_root = find_git_root(Path.cwd())
    now = time.time()

    if cmd == "diff":
        # cierra el turno abierto más reciente registrando qué se tocó
        for entry in reversed(log):
            if entry.get("open") and entry.get("prompt"):
                entry["open"] = False
                entry["endedEpoch"] = int(now)
                if git_root:
                    entry["touched"] = _changed_files_since(git_root, entry["startedEpoch"])
                _save_agent_log(ws, log)
                print(f"✅ turno cerrado: prompt='{entry['prompt'][:60]}' "
                      f"tocó={len(entry.get('touched', []))} archivo(s)")
                return 0
        print("⚠️ no hay turno abierto — correr `agentlog --prompt '...'` primero")
        return 1

    # cmd == "prompt": abre un turno nuevo
    entry = {
        "open": True,
        "startedEpoch": int(now),
        "startedIso": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "machine": socket.gethostname(),
        "project": git_root.name if git_root else None,
        "branch": None,
        "prompt": prompt[:500],
        "touched": [],
        "outOfScope": [],
    }
    if git_root:
        entry["branch"], _ = git(git_root, "branch", "--show-current")
    log.append(entry)
    _save_agent_log(ws, log)
    print(f"✅ turno abierto: prompt='{prompt[:60]}' · máquina={entry['machine']}")
    return 0


def _detect_out_of_scope(entry: dict) -> list:
    """Heurística simple de desviación: archivos tocados que no están mencionados
    en el prompt (ni por nombre ni por extensión/carpeta)."""
    prompt = (entry.get("prompt") or "").lower()
    prompt_tokens = set(prompt.replace("/", " ").replace(".", " ").replace("_", " ").split())
    out = []
    for f in entry.get("touched", []):
        f_low = f.lower()
        name = f_low.split("/")[-1].split(".")[0]
        ext = f_low.split(".")[-1] if "." in f_low else ""
        mentioned = (
            name in prompt_tokens
            or ext in prompt_tokens
            or any(tok in f_low for tok in prompt_tokens if len(tok) > 3)
        )
        if not mentioned:
            out.append(f)
    return out[:8]


def demo(ws: Path, days: int) -> int:
    """El demo de validación: todo en una salida presentable.
    Combina: qué hice + sin commitear + resume + bitácora del agente."""
    print("🧪 DEMO — LA MEMORIA DE TRABAJO DEL PROGRAMADOR")
    print("=" * 66)

    # 1) qué hice (whatdid)
    whatdid(ws, days)
    print()

    # 2) bitácora del agente (lo nuevo)
    log = _load_agent_log(ws)
    recent = [e for e in log if e.get("startedEpoch", 0) >= time.time() - days * 86400]
    if recent:
        print("\n🤖 BITÁCORA DEL AGENTE (qué pediste vs qué hizo):")
        for e in reversed(recent[-5:]):
            ts = datetime.fromtimestamp(e["startedEpoch"]).strftime("%H:%M")
            machine = "esta máquina" if e.get("machine") == socket.gethostname() else e.get("machine")
            print(f"\n  🕐 {ts} · {e.get('project') or '—'} · {machine}")
            print(f"     🗣️ Pediste: {e.get('prompt', '')[:90]}")
            touched = e.get("touched") or []
            if touched:
                sample = ", ".join(touched[:4])
                more = f" … y {len(touched) - 4} más" if len(touched) > 4 else ""
                print(f"     🔧 Tocó: {sample}{more}")
            out = _detect_out_of_scope(e)
            if out:
                print(f"     ⚠️ FUERA DE ALCANCE (¿lo pediste?): {', '.join(out[:4])}")
            elif e.get("touched") is None or e["touched"]:
                pass
            if e.get("open"):
                print(f"     ⏳ turno aún abierto — trabajo en progreso")
    else:
        print("\n🤖 BITÁCORA DEL AGENTE: sin turnos registrados en este período.")
        print("   (registrar con: continuity.py agentlog --prompt 'lo que pides' … --diff al terminar)")

    # 3) la pregunta de validación
    print("\n" + "=" * 66)
    print("❓ PREGUNTA DE VALIDACIÓN para el demo:")
    print("   '¿Usarías esto a diario si te dijera QUÉ se hizo, QUÉ quedó a medias,")
    print("    QUÉ tocó tu agente fuera de lo pedido, y dónde retomar — en cualquier")
    print("    máquina?' (Sí/No/Quizás + una frase de por qué)")
    return 0


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Continuidad de sesión entre máquinas")
    parser.add_argument("cmd", choices=["capture", "resume", "status", "whatdid", "agentlog", "demo"])
    parser.add_argument("--workspace", help="workspace alternativo (default: $CONTINUITY_WORKSPACE o carpeta sincronizada, ej. ~/Dropbox/workspace)")
    parser.add_argument("--days", type=int, default=1, help="período para whatdid/demo (default: 1 = ayer)")
    parser.add_argument("--prompt", default="", help="prompt del usuario para agentlog")
    parser.add_argument("--diff", action="store_true", help="cerrar turno de agentlog (registra qué cambió)")
    args = parser.parse_args()

    ws = Path(args.workspace).resolve() if args.workspace else workspace_dir()
    if args.cmd == "capture":
        state = capture(ws)
        print(f"✅ estado capturado: {state_path(ws)}")
        print(f"   máquina={state['lastMachine']} proyecto={state['project']} "
              f"branch={state['branch']} sin_commitear={len(state['uncommitted'])}")
        return 0
    if args.cmd == "resume":
        return resume(ws)
    if args.cmd == "status":
        return status(ws)
    if args.cmd == "whatdid":
        return whatdid(ws, args.days)
    if args.cmd == "agentlog":
        if args.diff:
            return agentlog(ws, "", "diff")
        return agentlog(ws, args.prompt, "prompt")
    if args.cmd == "demo":
        return demo(ws, args.days)
    return 1


if __name__ == "__main__":
    sys.exit(main())
