# Bitácora de trabajo — Smart-Claims Agent (TFM)

> Registro cronológico del trabajo realizado, pensado para explicar al equipo qué se ha
> hecho, por qué, y qué queda. Cada entrada indica: contexto, decisiones y cambios.
>
> **Convención mock vs. API real:** a lo largo del prototipo, las integraciones con los
> sistemas de Seguros Pepín están **simuladas (mock)** porque no tenemos acceso a sus APIs.
> Cada punto de simulación se marca con la nota `🔌 MOCK → API` explicando qué se haría con
> la integración real (qué sistema, qué endpoint, qué datos).

---

## 2026-06-23 — Sesión 1: análisis del repositorio y definición de plan

### Contexto de partida
- Estado real del repo: **esqueleto en fase temprana**. La documentación (README.md,
  CONTEXT_TFM.md) marcaba muchos componentes como "✅ Operativo" pero el código estaba
  en su mayoría sin implementar.
- Aclaraciones del equipo (recogidas esta sesión):
  - **Seguros Pepín es una empresa REAL** (la doc la llamaba "ficticia" — desactualizado).
  - **No tendremos acceso a las APIs de sus sistemas** → las integraciones externas se
    quedan como mock de forma **definitiva**, no temporal.
  - El **entregable de la Entrega 2 (26/06/2026)** es principalmente la **memoria escrita**:
    capítulos de **Arquitectura**, **Herramientas** y **Manual de usuario**. Adicionalmente
    se continúa el prototipo. Normativa APA 7.ª, en castellano.
  - La **UX/frontend no es prioritaria** ahora.

### Diagnóstico técnico (qué funcionaba y qué no)
| Componente | Estado real encontrado |
|---|---|
| Infra Docker (5 servicios) | ✅ Bien definida (`docker-compose.yml`) |
| 8 mock tools (`claim_tools.py`) | ✅ Completas y bien documentadas — lo más maduro |
| Orquestador "Agente A" | ⚠️ Grafo LangGraph parcial; agentes B–G son *stubs* vacíos |
| API REST `POST /claims` | ❌ Devuelve mensaje fijo, NO invoca al orquestador |
| `init_db()` | ❌ No crea el esquema (cuerpo vacío) |
| Agentes B, C, D, E, G | ❌ Sin implementar (`_stub` que devuelve `{}`) |
| Ciclo ReAct real | ❌ `triage` enruta una vez; los nodos no vuelven al orquestador |
| Bug de routing | ❌ Enruta a tool `resolve_claim` que no existe |
| Capa BD duplicada | ⚠️ `backend/db/` y `backend/app/db/` repetidas |
| Frontend Streamlit | ❌ Una línea con error de sintaxis (`st.titgle`) — irrelevante ahora |

### Decisión de enfoque
**Construir primero, documentar después.** Orden acordado con el equipo:
1. Completar el prototipo: implementar agentes B–G y la orquestación ReAct end-to-end,
   conectados a las mock tools, con persistencia de decisiones en MariaDB.
2. Redactar los tres capítulos de memoria sobre el prototipo ya funcional.

Razón: el Manual de usuario y el capítulo de Arquitectura deben describir un flujo que
realmente se ejecuta; así los ejemplos y capturas son reales.

### Pendiente al cierre de esta entrada
- [ ] Arreglar bloqueantes: `init_db`, conexión API→orquestador, bug routing `resolve_claim`.
- [ ] Implementar agentes B, C, D, E, G como nodos LangGraph con ciclo ReAct.
- [ ] Persistir decisiones de agentes (tabla `agent_decisions`).
- [ ] Consolidar capa BD duplicada.
- [ ] Redactar memoria: Arquitectura, Herramientas, Manual de usuario.
