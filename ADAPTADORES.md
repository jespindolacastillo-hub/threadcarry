# ADAPTADORES — threadcarry con cualquier agente

> El diferenciador: el estado vive en **archivos planos** que CUALQUIER agente
> puede leer. No depende de hooks de una plataforma específica. Aquí está cómo
> cada agente consume el mismo `.continuity/state.json`.

---

## Cómo funciona el patrón (los 3 puntos de integración)

```
1. AL INICIAR:  el agente corre `continuity.py resume`  → sabe dónde quedó
2. DURANTE:     el agente corre `continuity.py capture` → actualiza el estado
3. AL TERMINAR: el agente corre `continuity.py agentlog --diff` → cierra el turno
```

Cada agente tiene su mecanismo para "correr un comando al iniciar/terminar". El
estado es el MISMO archivo → todos los agentes comparten la misma memoria.

---

## 1. Claude Code (hooks — ya probado)

`install.sh` ya lo configura automáticamente. Manualmente:

```json
// ~/.claude/settings.json
{
  "hooks": {
    "SessionStart": [{ "matcher": "", "hooks": [{ "type": "command",
      "command": "python3 \"$WORKSPACE/.continuity/continuity.py\" resume 2>&1 || true" }] }],
    "Stop": [{ "matcher": "", "hooks": [{ "type": "command",
      "command": "python3 \"$WORKSPACE/.continuity/continuity.py\" capture 2>&1 || true" }] }]
  }
}
```

## 2. OpenAI Codex CLI (AGENTS.md nativo)

Codex CLI lee `AGENTS.md` del repo al iniciar — ponemos el resume ahí:

```markdown
<!-- AGENTS.md — agregar al final -->
## Continuidad (threadcarry)
Al iniciar, corre: python3 .continuity/continuity.py resume
Al terminar una tarea significativa, corre: python3 .continuity/continuity.py capture
```

(O en `~/.codex/config.toml` si quieres hooks reales cuando Codex los soporte.)

## 3. Google Gemini CLI (AGENTS.md también)

Gemini CLI respeta `AGENTS.md`/`CLAUDE.md` como contexto de proyecto:

```markdown
<!-- AGENTS.md -->
## Continuidad (threadcarry)
Primero: python3 .continuity/continuity.py resume
Al cerrar: python3 .continuity/continuity.py capture
```

## 4. Cursor (rules + commands)

- **Rules** (`Cursor Rules`): pegar el resume como contexto al inicio de cada
  agente: `@.continuity/continuity.py resume` — o simplemente una regla que diga
  "lee .continuity/state.json antes de trabajar".
- **Commands** (`.cursor/commands/`): un comando `resume` que corre el script.

## 5. DSH / cualquier GUI de agente

Cualquier agente que pueda ejecutar un comando o leer un archivo:
```
📄 .continuity/state.json   ← leer esto para saber dónde quedó la sesión
▶  python3 .continuity/continuity.py resume
```

---

## El patrón universal (si el agente NO tiene hooks)

```markdown
<!-- en AGENTS.md / CLAUDE.md / rules del proyecto -->
AL INICIAR: corre `python3 .continuity/continuity.py resume` y continúa donde quedó.
AL TERMINAR: corre `python3 .continuity/continuity.py capture` para registrar el estado.
```

Eso es todo. El agente solo necesita poder ejecutar python — y todos pueden.

---

## Estado de la integración

| Agente | Mecanismo | Estado |
|---|---|---|
| Claude Code | hooks (install.sh) | ✅ probado end-to-end |
| Codex CLI | AGENTS.md | 📝 documentado, pendiente probar |
| Gemini CLI | AGENTS.md | 📝 documentado, pendiente probar |
| Cursor | rules + commands | 📝 documentado, pendiente probar |
| Cualquier otro | AGENTS.md + comando | ✅ patrón universal documentado |
