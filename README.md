# Smart-Claims Agent

> **TFM — Máster en Machine Learning e Inteligencia Artificial**
> OBS Business School · Edición 2510
> Empresa de referencia: Seguros Pepín, S.A.

Sistema agéntico de procesamiento multimodal y ejecución autónoma para la gestión de reclamaciones de siniestros. El agente integra LLMs con capacidades de visión (VLM), razonamiento ReAct y recuperación semántica (RAG) para automatizar el ciclo completo de una reclamación: recepción, validación documental, verificación de cobertura, detección de fraude y resolución autónoma.

---

## Tabla de contenidos

1. [Arquitectura del sistema](#1-arquitectura-del-sistema)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Estructura del repositorio](#3-estructura-del-repositorio)
4. [Prerrequisitos](#4-prerrequisitos)
5. [Configuración del entorno](#5-configuración-del-entorno)
6. [Puesta en marcha con Docker](#6-puesta-en-marcha-con-docker)
7. [Servicios y URLs](#7-servicios-y-urls)
8. [Agentes implementados](#8-agentes-implementados)
9. [Base de datos](#9-base-de-datos)
10. [RAG y base de conocimiento](#10-rag-y-base-de-conocimiento)
11. [Mock APIs](#11-mock-apis)
12. [Frontend Streamlit](#12-frontend-streamlit)
13. [Testing](#13-testing)
14. [Flujo de trabajo del equipo](#14-flujo-de-trabajo-del-equipo)
15. [Variables de entorno](#15-variables-de-entorno)
16. [Decisiones de diseño](#16-decisiones-de-diseño)
17. [Registro de cambios](#17-registro-de-cambios)

---

## 1. Arquitectura del sistema

El sistema se organiza en cinco capas funcionales orquestadas por LangGraph con patrón ReAct (Reason → Act → Observe):

```
┌─────────────────────────────────────────────────────────────────┐
│  CAPA 1 — Canales de entrada                                    │
│  Email · Portal web · WhatsApp (simulado) · API REST            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│  CAPA 2 — Orquestación (Agente A)                               │
│  LangGraph + ReAct · Gestión de estado por expediente           │
│  Router de agentes · Human-in-the-Loop (HITL)                   │
└───────┬───────┬───────┬──────────┬───────────┬──────────────────┘
        │       │       │          │           │
       [B]     [C]     [D]        [E]         [G]
        │       │       │          │           │
┌───────▼───────▼───────▼──────────▼───────────▼──────────────────┐
│  CAPA 3 — Agentes especializados                                 │
│  B: Validación documental    C: Extracción VLM                  │
│  D: Cobertura RAG            E: Resolución autónoma             │
│  G: Fraude y cumplimiento                                        │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│  CAPA 4 — Datos y conocimiento                                  │
│  ChromaDB (pólizas, RAG) · MariaDB (log decisiones, HITL)       │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│  CAPA 5 — Integración simulada                                  │
│  Mock APIs Python: pagos · notificaciones · sistemas legacy      │
└─────────────────────────────────────────────────────────────────┘

  TRANSVERSAL T1: Seguridad (anonimización, control de acceso, auditoría)
  TRANSVERSAL T2: Observabilidad (trazas CoT, métricas, dashboard Streamlit)
```

### Flujo de una reclamación

```
Cliente envía reclamación
        │
        ▼
[A] Orquestador — triaje y enrutamiento
        │
        ├──► [G] Verificación OFAC/fraude (filtro temprano)
        │
        ├──► [B] Validación documental
        │         └── ¿Faltan documentos? → solicitar al cliente
        │
        ├──► [C] Extracción VLM (fotos, facturas, actas)
        │
        ├──► [D] Verificación de cobertura via RAG
        │
        └──► [E] Decisión autónoma
                  ├── Importe ≤ umbral → PAGO automático
                  ├── Importe > umbral → HITL (revisión humana)
                  └── Sin cobertura   → RECHAZO justificado
```

---

## 2. Stack tecnológico

| Componente | Tecnología | Versión |
|---|---|---|
| LLM / VLM | Claude (Anthropic) | claude-sonnet-4-20250514 |
| Framework agéntico | LangGraph + LangChain | 0.1.14 / 0.2.6 |
| Vector DB (RAG) | ChromaDB | 0.5.3 |
| Base de datos | MariaDB | 11.3 |
| Backend API | FastAPI + Uvicorn | 0.111.0 |
| Frontend demo | Streamlit | 1.36.0 |
| Lenguaje | Python | 3.11 |
| Contenerización | Docker + Compose | 25+ / 5.0+ |
| ORM | SQLAlchemy + Alembic | 2.0.31 |
| Driver BD async | aiomysql | 0.2.0 |
| OCR (fallback) | Tesseract | sistema |

---

## 3. Estructura del repositorio

```
TFM/                            # Raíz del repositorio Git
│
├── docker-compose.yml          # Orquestación de los 5 servicios
├── .env.example                # Plantilla de variables de entorno
├── .env                        # Variables reales (NO commitear)
├── .gitignore
├── setup.sh                    # Script de inicialización
├── README.md                   # Este documento
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # Entrypoint FastAPI
│   │   ├── agents/
│   │   │   ├── orchestrator.py # Agente A — LangGraph ReAct ✅
│   │   │   ├── agent_b.py      # Validación documental (pendiente)
│   │   │   ├── agent_c.py      # Extracción multimodal VLM (pendiente)
│   │   │   ├── agent_d.py      # Verificación cobertura RAG (pendiente)
│   │   │   ├── agent_e.py      # Resolución autónoma (pendiente)
│   │   │   └── agent_g.py      # Fraude y cumplimiento (pendiente)
│   │   ├── tools/
│   │   │   └── claim_tools.py  # Mock APIs (8 tools) ✅
│   │   ├── rag/
│   │   │   ├── ingest.py       # Ingesta de pólizas a ChromaDB (pendiente)
│   │   │   └── retriever.py    # Retriever semántico (pendiente)
│   │   ├── db/
│   │   │   ├── models.py       # Modelos SQLAlchemy ✅
│   │   │   └── session.py      # Gestión de conexión async ✅
│   │   └── routers/
│   │       ├── claims.py       # POST /api/v1/claims ✅
│   │       ├── agents.py       # GET  /api/v1/agents/status ✅
│   │       └── health.py       # GET  /health ✅
│   └── db/
│       └── init.sql            # Schema inicial + seed de demo ✅
│
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                  # Dashboard Streamlit (skeleton) ✅
│
├── data/
│   ├── synthetic/              # Dataset sintético de siniestros (.json)
│   └── policies/               # Documentos de pólizas para RAG (.pdf/.txt)
│
├── scripts/
│   ├── seed_dataset.py         # Genera el dataset sintético (pendiente)
│   └── ingest_policies.py      # Ingesta pólizas en ChromaDB (pendiente)
│
└── tests/
    ├── test_agents.py
    ├── test_tools.py
    └── test_rag.py
```

---

## 4. Prerrequisitos

### Software necesario

| Herramienta | Versión mínima | Verificación |
|---|---|---|
| Docker Desktop | 25.0 | `docker --version` |
| Docker Compose | 5.0 | `docker compose version` |
| Git | 2.40 | `git --version` |
| VSCode | cualquiera | — |
| Extensión WSL (si usas Windows) | — | Marketplace de VSCode |

### Clave de API de Anthropic

1. Ve a [console.anthropic.com](https://console.anthropic.com) y regístrate
2. **API Keys** → **Create Key** → nombre: `smart-claims-tfm`
3. Copia la clave — **solo se muestra una vez**

Formato: `sk-ant-api03-XXXX...`

### Importante: dónde instalar el proyecto (Windows + WSL)

Si trabajas en **Windows con WSL2**, instala el proyecto **dentro del filesystem de Linux**, no en `/mnt/c/...`. El rendimiento de Docker con volúmenes sobre el filesystem de Windows es muy bajo.

```bash
# ✅ Correcto — dentro de WSL
~/proyectos/TFM/

# ❌ Incorrecto — filesystem de Windows montado en WSL
/mnt/c/Users/tu_usuario/proyectos/TFM/
```

Para abrir el proyecto en VSCode desde WSL:

```bash
cd ~/proyectos/TFM
code .   # Requiere extensión WSL instalada en VSCode
```

---

## 5. Configuración del entorno

### 5.1 Clonar el repositorio

```bash
mkdir -p ~/proyectos
cd ~/proyectos
git clone https://github.com/[org]/TFM.git
cd TFM
```

### 5.2 Crear el fichero de variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y rellena como mínimo:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...   # Obligatorio
DB_ROOT_PASSWORD=root_dev             # Válido para dev
DB_PASSWORD=claims_dev                # Válido para dev
```

> ⚠️ **Nunca commitees el fichero `.env`**. Está incluido en `.gitignore`.

### 5.3 Crear ficheros que Git no versiona

Git no versiona directorios vacíos ni ficheros `__init__.py`. Ejecuta este bloque una sola vez tras clonar:

```bash
# __init__.py para que Python reconozca los módulos
touch backend/app/__init__.py \
      backend/app/agents/__init__.py \
      backend/app/tools/__init__.py \
      backend/app/rag/__init__.py \
      backend/app/db/__init__.py \
      backend/app/routers/__init__.py

# Directorios de datos y scripts
mkdir -p data/synthetic data/policies tests scripts
```

> ⚠️ **Si ves `ModuleNotFoundError: No module named 'app.X'`** al arrancar el backend, significa que el fichero no existe en disco. Créalo directamente desde el terminal de WSL con `cat`:
> ```bash
> cat > backend/app/db/session.py << 'EOF'
> # contenido del fichero
> EOF
> ```
> No copies ficheros desde Windows arrastrando — pueden quedar en la ruta incorrecta.

### 5.4 Verificar Docker Desktop con WSL (solo Windows)

Docker Desktop → Settings → Resources → WSL Integration → activa tu distribución Ubuntu.

```bash
docker info | grep "Operating System"
# Debe mostrar: Operating System: Docker Desktop
```

---

## 6. Puesta en marcha con Docker

### Primera vez

```bash
# Construye las imágenes (~5 minutos)
docker compose build

# Arranca todos los servicios en segundo plano
docker compose up -d

# Verifica el estado
docker compose ps
```

Salida esperada:

```
NAME            STATUS                   PORTS
sca-adminer     running                  0.0.0.0:8082->8080/tcp
sca-backend     running                  0.0.0.0:8000->8000/tcp
sca-chromadb    running                  0.0.0.0:8080->8000/tcp
sca-frontend    running (healthy)        0.0.0.0:8501->8501/tcp
sca-mariadb     running (healthy)        0.0.0.0:3306->3306/tcp
```

### Verificación rápida

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.2.0"}
```

### Comandos del día a día

```bash
docker compose logs -f                        # Logs de todos los servicios
docker compose logs -f backend                # Solo backend
docker compose down                           # Para servicios (conserva datos)
docker compose down -v                        # Para + elimina volúmenes ⚠️
docker compose up -d --build backend          # Rebuild tras cambiar requirements
docker exec -it sca-mariadb mariadb \
  -u claims_user -pclaims_dev smart_claims    # Acceso directo a la BD
```

### Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Can't connect to MySQL` | MariaDB aún inicializando | Esperar 20-30 s |
| Puerto 3306 ocupado | MySQL local corriendo | `sudo systemctl stop mysql` |
| `ModuleNotFoundError: No module named 'app.X'` | Fichero no creado en disco | Crear con `cat > fichero.py << 'EOF'` desde WSL |
| Build tarda más de 30 minutos | `llama-index` en requirements | Verificar que **no** está en `backend/requirements.txt` |
| Hot-reload muy lento | Proyecto en `/mnt/c/...` | Mover al filesystem de WSL |
| `docker: unknown command: docker composer` | Typo | Es `docker compose` sin 'r' al final |
| ChromaDB pierde datos | Se usó `down -v` | Usar siempre `down` sin `-v` |

---

## 7. Servicios y URLs

| Servicio | URL | Credenciales |
|---|---|---|
| **API REST** (Swagger UI) | http://localhost:8000/docs | — |
| **Frontend** (Streamlit) | http://localhost:8501 | — |
| **ChromaDB** (API) | http://localhost:8080 | — |
| **Adminer** (explorador DB) | http://localhost:8082 | servidor: `mariadb` · usuario: `claims_user` · pass: `claims_dev` · BD: `smart_claims` |

---

## 8. Agentes implementados

### Agente A — Orquestador (LangGraph ReAct) ✅

**Fichero:** `backend/app/agents/orchestrator.py`

Cerebro central del sistema. Recibe la reclamación, analiza el contenido y decide qué agente especializado debe intervenir. Gestiona el estado de cada expediente y activa el mecanismo HITL cuando el importe supera el umbral configurado.

- **Patrón:** ReAct (Reason → Act → Observe → Reason...)
- **Estado:** `ClaimState` (TypedDict con LangGraph)
- **HITL:** se activa cuando `amount > HITL_AMOUNT_THRESHOLD`

### Agente B — Validación documental *(pendiente)*

**Fichero:** `backend/app/agents/agent_b.py`

Verifica contrato vigente y documentación aportada. Llama al Agente G para el cribado OFAC antes de continuar el flujo. Solicita documentación adicional si es necesario.

**Pain points:** dependencia de procesos manuales · controles no integrados.

### Agente C — Extracción multimodal (VLM) *(pendiente)*

**Fichero:** `backend/app/agents/agent_c.py`

Extrae datos estructurados de facturas, fotografías de daños y actas usando Claude con visión. Fallback a OCR (Tesseract) para documentos de baja calidad.

**Pain points:** subjetividad en evaluación técnica · transcripción manual.

### Agente D — Verificación de cobertura (RAG) *(pendiente)*

**Fichero:** `backend/app/agents/agent_d.py`

Consulta ChromaDB con las pólizas de Seguros Pepín para determinar cobertura, importe máximo y franquicia. Devuelve el importe neto a pagar.

**Pain points:** falta de criterios estandarizados · controles manuales.

### Agente E — Resolución autónoma *(pendiente)*

**Fichero:** `backend/app/agents/agent_e.py`

Toma la decisión final y ejecuta la acción via Mock APIs. Registra el razonamiento completo (CoT) en MariaDB.

**Reglas:** cubierto + bajo umbral → pago · cubierto + alto umbral → HITL · no cubierto → rechazo · docs incompletos → solicitud.

### Agente G — Fraude y cumplimiento (LA/FT) *(pendiente)*

**Fichero:** `backend/app/agents/agent_g.py`

Verifica listas OFAC/ONU y calcula score de riesgo. Se invoca como **filtro de entrada**, alineado con política PEPIN-POL-CP-0006.

**Pain points:** compliance como filtro de salida · brecha en debida diligencia temprana.

---

## 9. Base de datos

### Schema (MariaDB 11.3)

**`claims`** — Expedientes

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | VARCHAR(36) | ID del expediente (PK) |
| `client_id` | VARCHAR(64) | Identificador del cliente |
| `claim_type` | VARCHAR(64) | Tipo de siniestro |
| `channel` | ENUM | Canal de entrada (email/web/whatsapp) |
| `status` | ENUM | Estado actual |
| `amount_requested` | DECIMAL | Importe reclamado |
| `amount_approved` | DECIMAL | Importe aprobado |

**`agent_decisions`** — Log CoT

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_id` | VARCHAR(36) | FK → claims |
| `agent` | VARCHAR(32) | Identificador del agente |
| `action` | VARCHAR(128) | Acción ejecutada |
| `reasoning` | TEXT | Razonamiento completo |
| `confidence` | FLOAT | Nivel de confianza |
| `hitl_required` | BOOLEAN | Si requirió revisión humana |

**`hitl_feedback`** — Revisión humana

| Campo | Tipo | Descripción |
|---|---|---|
| `decision_id` | BIGINT | FK → agent_decisions |
| `reviewer` | VARCHAR(128) | Identificador del revisor |
| `original_action` | VARCHAR(128) | Decisión original del agente |
| `final_action` | VARCHAR(128) | Decisión final tras revisión |
| `override_reason` | TEXT | Motivo del cambio |

### Acceso y consultas

```bash
docker exec -it sca-mariadb mariadb -u claims_user -pclaims_dev smart_claims

SELECT id, status, amount_requested FROM claims;
SELECT claim_id, agent, action, confidence FROM agent_decisions ORDER BY created_at DESC LIMIT 20;
```

### Migraciones (Alembic)

```bash
docker exec -it sca-backend alembic revision --autogenerate -m "descripcion"
docker exec -it sca-backend alembic upgrade head
docker exec -it sca-backend alembic current
```

---

## 10. RAG y base de conocimiento

Documentos de referencia en `data/policies/`:
- `SP-PCS-009` — Procedimiento reclamación estándar
- `SP-PCS-022` — Reclamación judicializada
- `SP-PCS-003` — Fianzas judiciales
- `PEPIN-POL-CP-0006` — Política de debida diligencia

```bash
# Ingesta inicial (una vez colocados los PDFs en data/policies/)
docker exec -it sca-backend python scripts/ingest_policies.py
curl http://localhost:8080/api/v1/collections
```

- **Colección:** `pepin_policies`
- **Embedding:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Chunk size:** 512 tokens · solapamiento: 50

---

## 11. Mock APIs

**Fichero:** `backend/app/tools/claim_tools.py`

| Tool | Descripción |
|---|---|
| `validate_documents` | Verifica documentación y contrato vigente |
| `extract_multimodal` | Extrae datos de imágenes y documentos via VLM |
| `check_policy` | Consulta cobertura y límites via RAG |
| `approve_payment` | Simula emisión de transferencia bancaria |
| `send_rejection` | Simula envío de email de rechazo |
| `request_more_info` | Simula solicitud de documentación adicional |
| `check_fraud` | Verifica OFAC y calcula score de riesgo |
| `log_decision` | Registra decisión y CoT en MariaDB |

---

## 12. Frontend Streamlit

**Fichero:** `frontend/app.py`

Dashboard de demostración con Chain of Thought visible, timeline de agentes, panel HITL y métricas de sesión.

```bash
open http://localhost:8501
docker compose logs -f frontend   # Hot-reload automático al guardar
```

---

## 13. Testing

```bash
docker exec -it sca-backend pytest tests/ -v
docker exec -it sca-backend pytest tests/ --cov=app --cov-report=term-missing
docker exec -it sca-backend pytest tests/test_e2e.py -v -s
```

| Escenario | Resultado esperado |
|---|---|
| Daños propios + docs completos + importe bajo | Pago automático |
| Daños propios + docs completos + importe alto | HITL activado |
| Tipo de siniestro no cubierto | Rechazo justificado |
| Documentación incompleta | Solicitud de información |
| Cliente en lista OFAC | Bloqueo en filtro temprano |
| Score de fraude alto | HITL activado |

---

## 14. Flujo de trabajo del equipo

### Ramas Git

```
main          ← rama estable, solo merge con PR aprobado
develop       ← rama de integración continua
feature/XXX   ← una rama por tarea
```

### Convención de commits

```
feat(agent-b): implementar validación documental
fix(rag): corregir chunking de PDFs escaneados
docs(readme): actualizar sección de setup
test(e2e): añadir caso de fraude OFAC
```

### Distribución de responsabilidades

| Rol | Tareas principales |
|---|---|
| Dev1 — LangGraph | Agentes A, C, E · Schema MariaDB |
| Dev2 — APIs & Tools | Agentes B, G · Mock APIs |
| RAG — Data Eng. | Dataset sintético · ChromaDB · Agente D |
| Frontend — UI | Streamlit app · Dashboard CoT |
| Doc — Técnico | Memoria E2 · Catálogo herramientas · Manual |
| Lead — QA | Integración E2E · Demo · Coordinación |

### Hitos de la Entrega 2

| Fecha | Hito |
|---|---|
| 25 mayo | Infraestructura operativa + Agente A funcionando |
| 15 junio | Code freeze: todos los agentes implementados |
| 22 junio | Demo grabada (vídeo ≤ 4 min) |
| **26 junio 23:59 CET** | **Entrega 2 en plataforma OBS** |

---

## 15. Variables de entorno

```bash
# ── LLM ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY=              # Clave API de Anthropic (obligatoria)

# ── MariaDB ──────────────────────────────────────────────────
DB_ROOT_PASSWORD=root_dev
DB_NAME=smart_claims
DB_USER=claims_user
DB_PASSWORD=claims_dev
DB_HOST=mariadb                 # Nombre del servicio Docker
DB_PORT=3306

# ── ChromaDB ─────────────────────────────────────────────────
CHROMA_HOST=chromadb            # Nombre del servicio Docker
CHROMA_PORT=8000
CHROMA_COLLECTION=pepin_policies

# ── Backend ──────────────────────────────────────────────────
BACKEND_URL=http://backend:8000

# ── Lógica de negocio ────────────────────────────────────────
HITL_AMOUNT_THRESHOLD=5000.0    # Importe (€) que activa revisión humana

# ── General ──────────────────────────────────────────────────
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## 16. Decisiones de diseño

| Decisión | Alternativas | Motivo |
|---|---|---|
| LangGraph sobre LangChain LCEL | LCEL · Autogen | Gestión de estado por expediente y HITL nativo |
| ChromaDB local | Pinecone · Weaviate | Sin coste, reproducible, sin dependencias cloud |
| MariaDB sobre SQLite | SQLite · PostgreSQL | Más cercana a producción, soporte DECIMAL para importes |
| `aiomysql` como driver BD | `pymysql` síncrono | FastAPI es async; `aiomysql` evita bloquear el event loop |
| Mock APIs sobre integraciones reales | — | Reproducibilidad en entorno académico, sin datos reales |
| Claude Sonnet sobre GPT-4o | GPT-4o · Mistral | Mejor rendimiento en español, tool use más estable |
| HITL por umbral de importe | HITL por confianza del modelo | Criterio auditable y comprensible por el negocio |
| `llama-index` excluido del build inicial | Incluirlo desde el inicio | Añade ~2 GB al build; se incorporará en S3 al implementar la ingesta RAG |

---

## 17. Registro de cambios

### v0.2.0 — Entrega 2 *(en curso)*

**Infraestructura — completado 15/05/2026**
- Docker Compose con 5 servicios operativos (backend, frontend, chromadb, mariadb, adminer)
- Schema MariaDB: tablas `claims`, `agent_decisions`, `hitl_feedback` + seed de demo
- FastAPI operativo: `/health`, `/api/v1/claims`, `/api/v1/agents/status`
- Modelos SQLAlchemy async (`session.py`, `models.py`)
- Agente A — Orquestador LangGraph ReAct
- Mock APIs completas (8 tools `@tool` LangChain)
- Frontend Streamlit skeleton operativo

**Pendiente**
- Dataset sintético de siniestros
- Agentes B, C, D, E, G
- Ingesta de pólizas en ChromaDB
- Dashboard Streamlit completo
- Tests E2E

### v0.1.0 — Entrega 1 *(entregada 08/05/2026)*
- Diagnóstico AS-IS del proceso de Seguros Pepín
- Diseño conceptual de la arquitectura agéntica
- Catálogo de agentes A–H con trazabilidad a pain points
- Stack tecnológico definido
- Roadmap del TFM
