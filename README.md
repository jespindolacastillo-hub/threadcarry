# threadcarry 🧵

**Tu agente de código pierde la memoria cada vez que cambias de computadora.**
**Threadcarry se la devuelve: abre tu agente en cualquier máquina y sabe
exactamente dónde quedaste — y qué hizo mientras no mirabas.**

> Continuidad de sesión entre máquinas, para cualquier agente, con cero
> infraestructura. Solo archivos + git.

---

## El problema

Trabajas a media tarea en la laptop → llegas a casa → abres tu agente en la otra
máquina → **no sabe nada**: ni en qué archivo ibas, ni qué quedó a medias, ni qué
tocó sin que lo pidieras. Los archivos viajan (Dropbox, Drive, OneDrive, Syncthing,
git). **La memoria de tu sesión, no.**

## La solución (30 segundos)

```bash
# en cualquier máquina, con cualquier agente:
threadcarry resume
```

```
⏭️  Sesión anterior: mi-laptop · hace 4 horas · 🌍 estás en OTRA máquina
📁 mi-proyecto · rama feat/auditoria
🔧 Estabas corrigiendo los 5 fixes de la auditoría E2E
⚠️ 2 archivos sin commitear: src/feature_a.js, docs/TODO.md
¿Continúo donde estabas?
```

Y con la **bitácora del agente**:

```
🤖 BITÁCORA DEL AGENTE:
   🕐 14:02 · Pediste: arreglar los fixes de paso3_wizard.html
   🔧 Tocó: paso3_wizard.html, dashboard_socios.html
   ⚠️ FUERA DE ALCANCE (¿lo pediste?): logo.png
   ⏳ Quedó a medias: listas negras (pendiente)
```

## Qué hace

| Comando | Qué responde |
|---|---|
| `threadcarry resume` | ¿Dónde quedó la última sesión? (máquina, proyecto, rama, sin commitear) |
| `threadcarry whatdid --days 1` | ¿Qué hice ayer? — todos tus repos en una pantalla |
| `threadcarry agentlog --prompt "..."` | Registra un turno del agente (qué pediste) |
| `threadcarry agentlog --diff` | Cierra el turno: qué tocó, qué quedó a medias, qué se desvió |
| `threadcarry demo` | Todo junto — la memoria de trabajo del programador |

## Cómo funciona

Un solo archivo de estado (`<workspace>/.continuity/state.json` + `agent-log.json`)
que viaja con tu workspace por **cualquier** transporte que ya uses. Sin servidor,
sin daemon, sin MCP, sin SDK. Cualquier agente que pueda leer un archivo puede
consumirlo — Claude Code, Codex, Gemini CLI, Cursor, DSH, el que salga mañana.

## Instalación

```bash
# 1. copia el script a tu workspace (o instala el paquete cuando salga)
cp continuity.py ~/tu-workspace/.continuity/continuity.py

# 2. registra el estado cuando trabajas (hooks opcionales)
python3 .continuity/continuity.py capture

# 3. al iniciar sesión, pregunta dónde quedaste
python3 .continuity/continuity.py resume
```

Multi-máquina: configura `CONTINUITY_WORKSPACE` o usa el workspace por defecto en
una carpeta sincronizada (Dropbox/Drive/OneDrive/Syncthing).

## Comparación honesta

| | threadcarry | passbaton | fleetpost | askscout |
|---|---|---|---|---|
| Multi-máquina | ✅ | ❌ local | ✅ | ❌ local |
| Trabajo SIN commitear visible | ✅ | ❌ | ❌ | ❌ |
| Bitácora del agente (desviación) | ✅ | ❌ | ❌ | ❌ |
| Cualquier agente (sin MCP) | ✅ | solo hooks | scripts | solo Claude |
| Cero infraestructura | ✅ | ✅ | requiere rclone | LLM API key |

## Roadmap

- [x] Estado vivo de sesión (`capture` / `resume`)
- [x] `whatdid` — memoria de trabajo del programador
- [x] Bitácora del agente con detección de desviación
- [x] `install.sh` de 1 línea (hooks automáticos para Claude Code)
- [x] Adaptadores documentados para Codex / Gemini / Cursor (ver `ADAPTADORES.md`)
- [ ] Resolución de conflictos entre máquinas
- [ ] Premium: multi-máquina + alertas + histórico semántico ($12-24/año)

## Documentación

- [ADAPTADORES.md](ADAPTADORES.md) — cómo integrar threadcarry con Claude Code,
  Codex CLI, Gemini CLI, Cursor y cualquier otro agente

## Licencia

MIT. Hecho con la frustración real de perder el hilo entre dos computadoras.
