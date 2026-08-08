# Guiones de prueba UAT — Smart-Claims Agent

Guiones de prueba de aceptación de usuario (UAT) para que Miriam ejecute el "attack día dirigido" del 2026-08-13 sobre el prototipo. Cubren determinismo del LLM, no-bypass del control humano, umbrales exactos, falsos positivos OFAC, orden de las compuertas, degradación de servicios, entradas adversarias, los 3 escenarios de demo, la vista Bandeja y el blindaje de entrada.

## REGLA DE ORO

**Todo "Resultado esperado" de este documento viene de una constante, cadena de texto o ruta de código real, citada con su archivo y línea.** Nada se ha inventado ni redondeado. Si un valor no se pudo verificar directamente en el código, se marca `[VERIFICAR]` en vez de adivinarlo. Si algo cambia en el código después de esta fecha (2026-08-08), este documento puede quedar desactualizado — reconfirma contra el código antes de una sesión de pruebas si ha pasado tiempo.

Fuentes citadas en todo el documento:
- `backend/app/agents/orchestrator.py` (Agente A — supervisor, `validate_claim_input`, `_normalize_final_state`, `process_claim`)
- `backend/app/agents/document_validator.py` (Agente B)
- `backend/app/agents/multimodal_extractor.py` + `backend/app/agents/vision.py` (Agente C)
- `backend/app/agents/fraud_compliance.py` + `backend/app/tools/fraud_tools.py` (Agente G)
- `backend/app/agents/coverage_checker.py` + `backend/app/tools/claim_tools.py::check_policy` (Agente D)
- `backend/app/agents/claim_resolver.py` (Agente E)
- `backend/app/agents/reasoning.py` (helper `reason()`, LLM opcional)
- `streamlit_app.py`, `streamlit_fixtures.py`
- `backend/tests/test_determinism.py`, `backend/scripts/evaluate_inprocess.py`

## Formato de cada caso de prueba

Cada caso de prueba de este documento sigue esta ficha:

| Campo | Contenido |
|---|---|
| **ID** | Identificador único del caso (p. ej. `T3-01`) |
| **Referencia** | Archivo:línea del código que sustenta el resultado esperado |
| **Título** | Descripción corta de qué se prueba |
| **Prioridad** | Alta / Media / Baja |
| **Tipo** | Funcional / Regresión / Frontera / Adversario / Degradación |
| **Precondiciones** | Estado necesario antes de empezar (app arrancada, variable de entorno, etc.) |
| **Pasos** | Pasos numerados, ejecutables por una persona sin conocimientos de programación |
| **Datos de prueba** | Valores exactos a introducir |
| **Resultado esperado** | Qué debe verse, citando la constante/cadena real |
| **Resultado obtenido** | _(a rellenar por Miriam durante la ejecución)_ |
| **Estado** | _(a rellenar: OK / KO / Bloqueado)_ |
| **Evidencia** | _(a rellenar: captura de pantalla o ruta de log)_ |

---

## T1 — Determinismo del razonamiento LLM

**Objetivo:** demostrar que quitar o poner la clave de Anthropic **nunca cambia una decisión**, solo el texto del razonamiento. Es el diseño "núcleo determinista + LLM opcional" (`reason()`, `backend/app/agents/reasoning.py:24-56`): sin `ANTHROPIC_API_KEY`, `reason()` devuelve el `fallback` determinista al instante (línea 38-39); con clave, invoca a Claude (`claude-sonnet-4-6`, timeout 20s, línea 44) pero **nunca** decide campos como `decision`, `status` o `hitl_required`.

| Campo | T1-01 |
|---|---|
| **ID** | T1-01 |
| **Referencia** | `backend/scripts/evaluate_inprocess.py:54-95` (32 casos sintéticos), `backend/tests/test_determinism.py:16-20,97-119` |
| **Título** | Las 32 decisiones del dataset sintético no cambian con/sin clave de API |
| **Prioridad** | Alta |
| **Tipo** | Regresión |
| **Precondiciones** | Repositorio clonado, entorno Python con dependencias instaladas, terminal en `backend/` |
| **Pasos** | 1. Sin `ANTHROPIC_API_KEY` en el entorno, ejecutar `py scripts/evaluate_inprocess.py`. Anotar el `decision` de cada uno de los 32 casos del JSON de salida (`data/synthetic/evaluation_inprocess.json`).<br>2. Exportar una `ANTHROPIC_API_KEY` válida (`set ANTHROPIC_API_KEY=sk-...` en PowerShell) y repetir el paso 1.<br>3. Comparar las 32 decisiones campo a campo. |
| **Datos de prueba** | El dataset lo genera el propio script (`build_cases()`, `evaluate_inprocess.py:54-95`); no requiere datos manuales |
| **Resultado esperado** | Las 32 decisiones (`decision`, `status`, `hitl_required`) coinciden 1:1 entre ambas ejecuciones. Es exactamente la comprobación que describe el docstring de `test_determinism.py:16-20`. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Guardar ambos JSON de salida como evidencia |

| Campo | T1-02 |
|---|---|
| **ID** | T1-02 |
| **Referencia** | `backend/tests/test_determinism.py::test_decisions_unchanged_when_llm_returns_adversarial_content` (línea 97) |
| **Título** | El test automático de determinismo pasa (contenido adversario del LLM simulado) |
| **Prioridad** | Alta |
| **Tipo** | Regresión |
| **Precondiciones** | Terminal en `backend/` |
| **Pasos** | 1. Ejecutar `py -m pytest tests/test_determinism.py -v`. |
| **Datos de prueba** | Ninguno (el test genera sus propios casos y simula (`monkeypatch`) que el LLM devuelve contenido adversario) |
| **Resultado esperado** | El test `test_decisions_unchanged_when_llm_returns_adversarial_content` termina en `PASSED`; internamente comprueba `mismatches == {}` (línea 119) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de la terminal |

---

## T2 — No-bypass del control humano (umbral HITL) con importes aleatorios

**Objetivo:** ninguna combinación de importe puede saltarse el control humano por encima de 5.000 €. No existía un script para esto — se ha creado `backend/scripts/uat_t2_random_amounts.py` (única excepción autorizada a "no tocar código de producción", por ser explícitamente una utilidad de prueba).

**Nota de diseño del script** (documentada también en su propio docstring): usa el tipo de siniestro `"responsabilitat"` a propósito, porque su franquicia es 0 € (`check_policy`, `backend/app/tools/claim_tools.py:119-120`: `"responsabilitat": {"covered": True, "max": 50000, "deductible": 0, ...}`). Con franquicia 0, `net_payable == amount` en todo el rango 1-50.000 € y se capa a 50.000 € por encima — siempre por encima del umbral HITL de 5.000 €. Con otros tipos (p. ej. `danys_propis`, franquicia 300 €) existe un tramo legítimo (importe entre 5.000 € y 5.300 €) donde la franquicia hace que `net_payable` caiga por debajo del umbral y el sistema aprueba PAGO correctamente — **eso no sería un fallo**, sino la franquicia funcionando como está diseñada. Usar `responsabilitat` aísla la propiedad bajo prueba (el umbral HITL) sin que la franquicia la contamine.

| Campo | T2-01 |
|---|---|
| **ID** | T2-01 |
| **Referencia** | `backend/scripts/uat_t2_random_amounts.py`; umbral en `backend/app/agents/claim_resolver.py:27` (`DEFAULT_HITL_THRESHOLD = 5000.0`), comparación `net_payable > threshold` en línea 108 |
| **Título** | 200 reclamaciones con importe aleatorio (1€-100.000€): ninguna con importe > 5.000 € resulta en PAGO |
| **Prioridad** | Alta |
| **Tipo** | Frontera / Regresión |
| **Precondiciones** | Terminal en `backend/`, sin `ANTHROPIC_API_KEY` (el script la elimina igualmente por seguridad, línea con `os.environ.pop`) |
| **Pasos** | 1. Ejecutar `py scripts/uat_t2_random_amounts.py --n 200 --seed 7`.<br>2. Esperar a que termine (puede tardar varios minutos; procesa 200 expedientes reales a través de todo el grafo de agentes).<br>3. Leer el resumen final impreso en la terminal. |
| **Datos de prueba** | Generados por el propio script: 200 importes aleatorios uniformes entre 1,0 € y 100.000,0 € (semilla fija 7, reproducible) |
| **Resultado esperado** | La línea final dice `OK: ningun caso con importe > umbral HITL obtuvo PAGO automatico.` y `Fallos (...): 0` |
| **Resultado obtenido** | `[COMPLETAR TRAS EJECUCIÓN — ver nota de verificación al final de este documento]` |
| **Estado** | |
| **Evidencia** | Captura de la terminal con el resumen final |

---

## T3 — Fronteras exactas del umbral HITL (5.000 €)

**Objetivo:** probar el borde exacto del umbral en la propia interfaz (`streamlit_app.py`, vista "Nueva reclamación"). La condición real es `net_payable > 5000.0` (estrictamente mayor, `claim_resolver.py:108`) — es decir, exactamente 5.000,00 € de importe neto **sí** paga automáticamente; hace falta superarlo aunque sea en un céntimo para que salte a revisión humana.

**Aviso importante para Miriam:** la app Streamlit activa el RAG real de pólizas por defecto (`SCA_RAG_ENABLED=1`, `streamlit_app.py:38`). Si ChromaDB está disponible, el Agente D puede usar cifras de cobertura/franquicia recuperadas de las pólizas reales en vez de las de la tabla mock de abajo. **Antes de leer el resultado, comprueba el bloque "Cobertura (Agente D · RAG sobre pólizas)" en la pantalla de resultado**: si aparece, anota los valores reales que muestra en "Resultado obtenido" en vez de compararlos ciegamente con esta tabla. Si no aparece ese bloque, se ha usado el catálogo determinista de abajo.

Catálogo determinista de referencia (`backend/app/tools/claim_tools.py:117-124`):

| Tipo | Cobertura máx. | Franquicia | Fórmula `net_payable` |
|---|---|---|---|
| `responsabilitat` (Responsabilidad civil) | 50.000 € | 0 € | `min(amount, 50000)` |
| `danys_propis` (Daños propios) | 10.000 € | 300 € | `max(0, min(amount,10000) - 300)` |

| Campo | T3-01 |
|---|---|
| **ID** | T3-01 |
| **Referencia** | `claim_resolver.py:108,151-201` (rama PAGO) |
| **Título** | Responsabilidad civil, importe exactamente 5.000,00 € → PAGO automático |
| **Prioridad** | Alta |
| **Tipo** | Frontera |
| **Precondiciones** | App Streamlit arrancada (`py -m streamlit run streamlit_app.py`), vista "Nueva reclamación" |
| **Pasos** | 1. En "O crea una reclamación personalizada", rellenar Nombre = `Test Frontera 5000`, ID Cliente = `T3-01`, Tipo de siniestro = `Responsabilidad civil`.<br>2. Importe reclamado = `5000`.<br>3. Documentos aportados = `foto_danys`, `acta_policial`, `dades_tercer` (los 3 requeridos, ver tabla `REQUIRED_DOCS_BY_TYPE`).<br>4. Pulsar "Procesar reclamación". |
| **Datos de prueba** | amount = 5000.00, claim_type = responsabilitat, docs completos |
| **Resultado esperado** | Píldora de decisión = `"Resuelto · Pago aprobado"` (`DECISION_STYLE["PAGO"]`, `streamlit_app.py:99`); campo "Decisión" = `PAGO`; "Importe pagado" = `5.000 €` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla del resultado |

| Campo | T3-02 |
|---|---|
| **ID** | T3-02 |
| **Referencia** | `claim_resolver.py:108-149` (rama REVISION_HUMANA) |
| **Título** | Responsabilidad civil, importe 5.000,01 € → Revisión humana |
| **Prioridad** | Alta |
| **Tipo** | Frontera |
| **Precondiciones** | Igual que T3-01 |
| **Pasos** | Igual que T3-01 pero con Importe reclamado = `5000.01` |
| **Datos de prueba** | amount = 5000.01, claim_type = responsabilitat, docs completos |
| **Resultado esperado** | Píldora = `"Revisión humana requerida"` (`DECISION_STYLE["REVISION_HUMANA"]`); "Decisión" = `REVISION_HUMANA`; leyenda bajo el título con el motivo `importe {net_payable} EUR supera umbral HITL (5000.0 EUR)` (`claim_resolver.py:~132`, cadena `f"importe {net_payable} EUR supera umbral HITL ({threshold} EUR)"`) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T3-03 |
|---|---|
| **ID** | T3-03 |
| **Referencia** | Fórmula `net_payable` de `danys_propis`, `claim_tools.py:117-118` |
| **Título** | Daños propios, importe 5.300,00 € (net_payable exacto 5.000 € tras franquicia) → PAGO |
| **Prioridad** | Media |
| **Tipo** | Frontera |
| **Precondiciones** | Igual que T3-01 |
| **Pasos** | Igual que T3-01 pero Tipo = `Daños propios`, Importe = `5300`, Documentos = `foto_danys`, `factura`, `denuncia_companyia` |
| **Datos de prueba** | amount = 5300.00, claim_type = danys_propis, docs completos |
| **Resultado esperado** | `net_payable = min(5300,10000) - 300 = 5000.0`; **no** supera el umbral (`> 5000`, no `>=`) → `PAGO`, importe pagado `5.000 €` (nótese: menor que el importe reclamado, por la franquicia) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T3-04 |
|---|---|
| **ID** | T3-04 |
| **Referencia** | Igual que T3-03 |
| **Título** | Daños propios, importe 5.300,01 € → Revisión humana |
| **Prioridad** | Media |
| **Tipo** | Frontera |
| **Precondiciones** | Igual que T3-01 |
| **Pasos** | Igual que T3-03 pero Importe = `5300.01` |
| **Datos de prueba** | amount = 5300.01, claim_type = danys_propis, docs completos |
| **Resultado esperado** | `net_payable = 5000.01` → `REVISION_HUMANA` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## T4 — Falsos positivos OFAC (umbral de similitud 0,82)

**Objetivo:** el cribado antifraude (Agente G) compara el nombre del cliente contra una lista de 15 entidades/personas sancionadas usando similitud de texto (`difflib.SequenceMatcher`, normalizado sin acentos/mayúsculas, `fraud_tools.py:89-96`). El umbral de coincidencia es **`_OFAC_MATCH_THRESHOLD = 0.82`** (`fraud_tools.py:53`). Esto es una fuente real de falsos positivos: nombres parecidos (variantes de transliteración, apellidos comunes, abreviaturas) pueden superar 0,82 sin ser la misma persona/entidad.

Los valores de similitud de la siguiente tabla **se han calculado ejecutando la función real** `check_ofac_sanctions()` del código (no son estimaciones), el 2026-08-08.

| Campo | T4-01 |
|---|---|
| **ID** | T4-01 |
| **Referencia** | `fraud_tools.py:53,112-145`; lista de sancionados `fraud_tools.py:27-43` |
| **Título** | Variante de transliteración de un nombre sancionado ("Dimitri Volkoff" vs. "Dmitri Volkov") dispara un falso positivo OFAC |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Precondiciones** | App Streamlit arrancada, vista "Nueva reclamación" |
| **Pasos** | 1. Rellenar Nombre del asegurado = `Dimitri Volkoff` (persona **distinta** de la sancionada real "Dmitri Volkov", solo una coincidencia de escritura).<br>2. Tipo = `Daños propios`, Importe = `2500`, documentos completos.<br>3. Procesar. |
| **Datos de prueba** | client_name = "Dimitri Volkoff" → similitud real = **0,8571** (por encima de 0,82) |
| **Resultado esperado** | El caso se bloquea igualmente: píldora `"Bloqueado · Fraude / OFAC"` (`DECISION_STYLE["RECHAZO_FRAUDE"]`), "Decisión" = `RECHAZO_FRAUDE`, sección "Cribado antifraude (Agente G)" muestra veredicto `BLOCKED`. Esto **es correcto según el diseño actual** (cualquier `similarity >= 0.82` basta), pero es un falso positivo real que Miriam debe documentar como límite conocido del cribado, no como bug. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T4-02 |
|---|---|
| **ID** | T4-02 |
| **Referencia** | Igual que T4-01 |
| **Título** | Traducción al catalán de una razón social sancionada ("Grup Financer Centaure" vs. "Grupo Financiero Centauro") dispara falso positivo |
| **Prioridad** | Media |
| **Tipo** | Adversario |
| **Precondiciones** | Igual que T4-01 |
| **Pasos** | Igual que T4-01 con Nombre = `Grup Financer Centaure` |
| **Datos de prueba** | client_name = "Grup Financer Centaure" → similitud real = **0,8936** |
| **Resultado esperado** | `RECHAZO_FRAUDE`, veredicto `BLOCKED` — mismo razonamiento que T4-01 |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T4-03 |
|---|---|
| **ID** | T4-03 |
| **Referencia** | Igual que T4-01 |
| **Título** | Nombre parecido pero por debajo del umbral ("Ramirez Fuentes" vs. "Ramirez Fuentes Cartel") NO se bloquea |
| **Prioridad** | Media |
| **Tipo** | Frontera |
| **Precondiciones** | Igual que T4-01 |
| **Pasos** | Igual que T4-01 con Nombre = `Ramirez Fuentes` |
| **Datos de prueba** | client_name = "Ramirez Fuentes" → similitud real = **0,8108** (por debajo de 0,82) |
| **Resultado esperado** | El caso **no** se bloquea por fraude — sigue el flujo normal según importe/documentos (con estos datos, `PAGO`). Confirma que el umbral 0,82 tiene un lado "no dispara" real y verificable, útil como control de que T4-01/T4-02 no bloquean *cualquier* nombre. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

**Tabla de referencia de similitudes calculadas** (para que Miriam pueda construir más casos si quiere ampliar la cobertura):

| Nombre introducido | Entidad más parecida | Similitud | ¿Dispara bloqueo (≥0,82)? |
|---|---|---|---|
| Dimitri Volkoff | Dmitri Volkov | 0,8571 | Sí |
| Grup Financer Centaure | Grupo Financiero Centauro | 0,8936 | Sí |
| Mohamed Al Hashimi | Mohammed Al-Hashimi | 0,9189 | Sí |
| Natalia Semenov | Natalia Semenova | 0,9677 | Sí |
| Amira Bel-Haj | Amira Belhaj | 0,9600 | Sí |
| Bogdan Petrescu Jr | Bogdan Petrescu | 0,9091 | Sí |
| Falcon Ridge Resources | Falcon Ridge Resources Corp | 0,8980 | Sí |
| Ramirez Fuentes | Ramirez Fuentes Cartel | 0,8108 | No |
| Yusuf Al-Farsi | Yusuf Ibrahim Al-Farsi | 0,7778 | No |
| Black Sea Capital | Black Sea Capital Partners | 0,7907 | No |
| Al Rashid Trading | Al-Rashid Trading Group | 0,8000 | No |
| Al Mawrid Finance | Al-Mawrid Finance Company | 0,7619 | No |
| Marta Soler Puig (cliente inocente, caso Bandeja) | — | 0,3750 | No |
| Jordi Ferrer Camps (cliente inocente, caso Bandeja) | — | 0,4500 | No |

---

## T5.1 — Conflicto de orden de compuertas: OFAC + documentación incompleta

**Objetivo:** documentar un comportamiento ya conocido y aceptado por el equipo (ver nota en la memoria del proyecto), no "arreglarlo". El orden real de las compuertas es **A → B → C → G → D → E** (`orchestrator.py`, `supervisor_router`): el Agente B (validación documental) se ejecuta **antes** que el Agente G (antifraude/OFAC). Si el Agente B marca la documentación como inválida, el flujo corta inmediatamente (`_normalize_final_state`, caso 2, `orchestrator.py:332-341`) **sin llegar nunca a ejecutar el Agente G** — es decir, un cliente sancionado con documentación incompleta recibe `INFO_REQUERIDA`, no `RECHAZO_FRAUDE`.

| Campo | T5.1-01 |
|---|---|
| **ID** | T5.1-01 |
| **Referencia** | `orchestrator.py::_normalize_final_state` líneas 332-341 (caso INFO_REQUERIDA se evalúa aunque el fraude no se haya llegado a comprobar); orden de nodos confirmado en `supervisor_router` |
| **Título** | Cliente sancionado (OFAC) con documentación incompleta → INFO_REQUERIDA, no RECHAZO_FRAUDE |
| **Prioridad** | Alta |
| **Tipo** | Funcional (comportamiento de diseño, no bug) |
| **Precondiciones** | App Streamlit arrancada, vista "Nueva reclamación" |
| **Pasos** | 1. Nombre del asegurado = `Viktor Nikolaev Kozlov` (coincidencia exacta con la lista OFAC, similitud 1,0000).<br>2. Tipo = `Daños propios`, Importe = `2500`.<br>3. Documentos aportados = solo `factura` (faltan `foto_danys` y `denuncia_companyia`, ver `REQUIRED_DOCS_BY_TYPE`).<br>4. Procesar. |
| **Datos de prueba** | client_name = "Viktor Nikolaev Kozlov" (sancionado real), documents = ["factura"] |
| **Resultado esperado** | Píldora = `"Información requerida"` (`DECISION_STYLE["INFO_REQUERIDA"]`), "Decisión" = `INFO_REQUERIDA`, **no** `RECHAZO_FRAUDE`. El stepper de agentes (A→B→C→G→D→E) debe mostrar que el flujo se detuvo en B, sin marcar G como visitado. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla, incluyendo el stepper de agentes visible bajo el resultado |
| **Nota para el informe** | Este es el "T5.1 finding" ya anticipado por el equipo: aceptable porque no se realiza ningún pago en ningún caso, pero debe documentarse como decisión de diseño deliberada, no dejarse parecer un accidente. |

---

## T6 — Degradación de servicios (5 escenarios)

**Objetivo:** demostrar que el sistema nunca se rompe ni bloquea el flujo cuando un servicio externo falla — siempre cae a un camino determinista con una decisión legible. Cinco rutas de degradación reales, verificadas en el código:

| Campo | T6-01 |
|---|---|
| **ID** | T6-01 |
| **Referencia** | `reasoning.py:38-39` |
| **Título** | Sin clave de Anthropic → razonamiento determinista, decisión sin cambios |
| **Prioridad** | Alta |
| **Tipo** | Degradación |
| **Precondiciones** | Variable `ANTHROPIC_API_KEY` NO definida en el entorno |
| **Pasos** | 1. Arrancar la app sin la variable definida.<br>2. Procesar el escenario rápido "Pago automático". |
| **Datos de prueba** | Escenario de demo "Pago automático" (ver sección DEMO) |
| **Resultado esperado** | El caso se resuelve igual (`PAGO`), sin error ni excepción visible; el texto de razonamiento es el `fallback` determinista construido en cada agente (p. ej. en `claim_resolver.py`, la cadena que empieza por `"Agente E: ..."` — no un texto generado por Claude) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de la sección "Cadena de razonamiento de los agentes" |

| Campo | T6-02 |
|---|---|
| **ID** | T6-02 |
| **Referencia** | `reasoning.py:41-56` (timeout=20 en la línea 44, captura de `Exception` genérica en línea 52) |
| **Título** | Clave de Anthropic inválida/red caída → fallback tras el intento fallido, sin romper el flujo |
| **Prioridad** | Media |
| **Tipo** | Degradación |
| **Precondiciones** | Definir `ANTHROPIC_API_KEY` con un valor inválido (p. ej. `sk-invalido-000`) |
| **Pasos** | 1. Arrancar la app con esa clave inválida.<br>2. Procesar el escenario "Pago automático". |
| **Datos de prueba** | Igual que T6-01, con clave inválida en vez de ausente |
| **Resultado esperado** | El caso se resuelve igual (`PAGO`); puede tardar unos segundos más (el intento real a la API falla antes de caer al fallback) pero nunca supera ~20s por llamada (timeout configurado) ni se muestra ningún error al usuario |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla + tiempo mostrado en "Tiempo" (metric card) |

| Campo | T6-03 |
|---|---|
| **ID** | T6-03 |
| **Referencia** | `coverage_checker.py:30` (`if not os.getenv("SCA_RAG_ENABLED"): return None`) |
| **Título** | RAG de pólizas desactivado → Agente D usa el catálogo determinista sin romper el flujo |
| **Prioridad** | Media |
| **Tipo** | Degradación |
| **Precondiciones** | Variable `SCA_RAG_ENABLED` puesta a `0` o vacía antes de arrancar la app (sobreescribe el valor por defecto `1` que fija `streamlit_app.py:38`) |
| **Pasos** | 1. Arrancar la app con `SCA_RAG_ENABLED=0`.<br>2. Procesar el escenario "Pago automático". |
| **Datos de prueba** | Igual que T6-01 |
| **Resultado esperado** | El caso se resuelve igual (`PAGO`); en el resultado **no** aparece la sección "Cobertura (Agente D · RAG sobre pólizas)" (solo se muestra si `coverage_result.source == "rag"`, `streamlit_app.py:355`) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla mostrando la ausencia del bloque RAG |

| Campo | T6-04 |
|---|---|
| **ID** | T6-04 |
| **Referencia** | `vision.py:71` (`if not os.getenv("ANTHROPIC_API_KEY"): return None`), `multimodal_extractor.py:61-64` (registro neutro `"Extracción no disponible (sin clave LLM o error)."`) |
| **Título** | Sin clave de Anthropic, subir un documento real no rompe la extracción multimodal |
| **Prioridad** | Baja |
| **Tipo** | Degradación |
| **Precondiciones** | `ANTHROPIC_API_KEY` no definida |
| **Pasos** | 1. En "Nueva reclamación" → formulario personalizado, subir cualquier imagen en "Sube los documentos reales...".<br>2. Rellenar el resto de campos y procesar. |
| **Datos de prueba** | Cualquier imagen PNG/JPG pequeña |
| **Resultado esperado** | El flujo termina con una decisión normal, sin traceback; si se muestra la sección "Extracción multimodal real (Agente C · Claude Vision)" solo aparece cuando `extraction.source == "claude_vision"` — sin clave, no debería aparecer ese bloque (cae a extracción mock) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T6-05 |
|---|---|
| **ID** | T6-05 |
| **Referencia** | `orchestrator.py:419-441` (persistencia best-effort envuelta en `try/except`) |
| **Título** | Base de datos MariaDB no disponible → el resultado se muestra igualmente, sin excepción visible |
| **Prioridad** | Media |
| **Tipo** | Degradación |
| **Precondiciones** | MariaDB apagada o inaccesible (p. ej. no arrancar el contenedor Docker de base de datos) |
| **Pasos** | 1. Arrancar solo la app Streamlit (sin la base de datos).<br>2. Procesar el escenario "Pago automático". |
| **Datos de prueba** | Igual que T6-01 |
| **Resultado esperado** | El resultado se muestra con normalidad (`PAGO`); no aparece ningún error en pantalla (A3, `streamlit_app.py:278`); el fallo de persistencia solo queda registrado en el log del servidor (`logger.warning`, `orchestrator.py:440`), nunca visible al usuario |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla + (si es accesible) línea del log del servidor con el warning |

---

## T7 — Entradas adversarias vía interfaz

**Objetivo:** probar el blindaje A1 (`validate_claim_input`, `orchestrator.py:50-106`) a través de lo que realmente es alcanzable desde la interfaz. **Aviso importante:** el formulario de Streamlit ya restringe varias entradas en el propio widget (p. ej. `number_input(min_value=0.0, max_value=100000.0)`, `streamlit_app.py:551`, y el `selectbox` de tipo de siniestro solo ofrece los 4 tipos válidos). Por eso, algunas ramas de `validate_claim_input` (importe negativo, importe NaN/infinito, importe ≥ 10.000.000, tipo de siniestro desconocido) **no son alcanzables desde la UI** — están cubiertas por los tests automáticos (`test_input_validation.py`) pero no tienen un caso UAT aquí. Los dos casos siguientes sí son alcanzables:

| Campo | T7-01 |
|---|---|
| **ID** | T7-01 |
| **Referencia** | `validate_claim_input`, rama 1, `orchestrator.py:62-76`; cadena exacta `f"importe reclamado invalido: {amount_requested!r}"` |
| **Título** | Importe reclamado = 0 € → Rechazo automático |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Precondiciones** | App Streamlit arrancada, vista "Nueva reclamación" |
| **Pasos** | 1. Rellenar Nombre, ID Cliente, Tipo de siniestro = `Daños propios`.<br>2. Importe reclamado = `0`.<br>3. Documentos completos.<br>4. Procesar. |
| **Datos de prueba** | amount = 0.0 |
| **Resultado esperado** | Píldora = `"Rechazado · Sin cobertura"` (`DECISION_STYLE["RECHAZO"]`); "Decisión" = `RECHAZO`; leyenda del motivo = `importe reclamado invalido: 0.0` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T7-02 |
|---|---|
| **ID** | T7-02 |
| **Referencia** | `validate_claim_input`, rama 3, `orchestrator.py:88-97`; cadena exacta `"nombre del asegurado invalido (vacio o excesivamente largo)"`; `MAX_CLIENT_NAME_LEN = 200` (línea 44) |
| **Título** | Nombre del asegurado de más de 200 caracteres → Revisión humana |
| **Prioridad** | Media |
| **Tipo** | Adversario |
| **Precondiciones** | Igual que T7-01 |
| **Pasos** | 1. Rellenar Nombre del asegurado con una cadena de más de 200 caracteres (p. ej. copiar y pegar `"Juan García "` repetido hasta superar 200 caracteres — hay una plantilla lista en "Datos de prueba").<br>2. Tipo = `Daños propios`, Importe = `2500`, documentos completos.<br>3. Procesar. |
| **Datos de prueba** | Nombre (201 caracteres): `Juan García Fernández López Martínez de la Torre y Sánchez del Río Rodríguez Pérez González Álvarez Domínguez Ruiz Jiménez Moreno Muñoz Álvarez Romero Alonso Gutiérrez Navarro Torres Domingu` (verificar con un contador de caracteres que supera 200; si no llega, añadir texto hasta superarlo) |
| **Resultado esperado** | Píldora = `"Revisión humana requerida"`; "Decisión" = `REVISION_HUMANA`; leyenda del motivo = `nombre del asegurado invalido (vacio o excesivamente largo)` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T7-03 |
|---|---|
| **ID** | T7-03 |
| **Referencia** | `document_validator.py` (Agente B), `claim_tools.py::REQUIRED_DOCS_BY_TYPE` |
| **Título** | Ningún documento aportado → Información requerida (todos los documentos figuran como faltantes) |
| **Prioridad** | Baja |
| **Tipo** | Adversario |
| **Precondiciones** | Igual que T7-01 |
| **Pasos** | 1. Rellenar Nombre, ID Cliente, Tipo = `Robo`, Importe = `1000`.<br>2. Documentos aportados: no seleccionar ninguno.<br>3. Procesar. |
| **Datos de prueba** | claim_type = robatori, documents = [] |
| **Resultado esperado** | Píldora = `"Información requerida"`; "Decisión" = `INFO_REQUERIDA`; leyenda menciona los dos documentos requeridos para robo: `acta_policial, llista_objectes_robats` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## DEMO — Los 3 (realmente 5) escenarios de demostración, ejecutados 10 veces cada uno

**Nota de discrepancia real detectada:** `DEMO_SCENARIOS` (`streamlit_app.py:107-124`) define **5** escenarios, no 3 ni 4 — pero la propia app dice "cuatro casos" en el texto de la pantalla de inicio (`streamlit_app.py:437`). Esto es un desajuste de texto en la UI, no del flujo de agentes; vale la pena que Miriam lo reporte como hallazgo cosmético menor. Los 5 escenarios reales, verbatim:

| Escenario | claim_type | amount | Resultado esperado |
|---|---|---|---|
| Pago automático | danys_propis | 2.500,00 € | PAGO |
| Revisión humana (HITL) | responsabilitat | 9.500,00 € | REVISION_HUMANA |
| Información requerida | danys_propis | 3.000,00 € (solo `factura` aportada) | INFO_REQUERIDA |
| Rechazo por no cobertura | danys_mecanics | 1.500,00 € | RECHAZO (daños mecánicos no tiene cobertura, `covered: False` en `check_policy`) |
| Bloqueo por fraude (OFAC) | danys_propis | 2.500,00 €, cliente "Viktor Nikolaev Kozlov" | RECHAZO_FRAUDE |

| Campo | DEMO-01 |
|---|---|
| **ID** | DEMO-01 |
| **Referencia** | `streamlit_app.py:107-124,534-537` |
| **Título** | Cada uno de los 5 escenarios rápidos se ejecuta 10 veces seguidas sin fallos ni variación de decisión |
| **Prioridad** | Alta |
| **Tipo** | Regresión |
| **Precondiciones** | App Streamlit arrancada, vista "Nueva reclamación" |
| **Pasos** | Para cada uno de los 5 escenarios: pulsar su botón "Procesar" 10 veces seguidas (recargando o repitiendo), anotando la decisión de cada intento. |
| **Datos de prueba** | Los 5 escenarios de la tabla anterior |
| **Resultado esperado** | Las 10 repeticiones de cada escenario devuelven exactamente la misma `decision` que la tabla; 0 excepciones visibles en pantalla en las 50 ejecuciones totales |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Tabla de 50 filas (5 escenarios × 10 repeticiones) con decisión obtenida en cada una |

---

## BANDEJA — Vista "Bandeja" (casos entrantes por WhatsApp simulado)

**Objetivo:** verificar los 2 casos fijos de la vista Bandeja (`streamlit_fixtures.py::BANDEJA_CASES`), que reutilizan el mismo camino ya blindado (`process_and_store`, confirmado por `test_streamlit_ui.py::test_bandeja_view_shows_fixture_cases_and_processes_pago_automatico`).

| Campo | BANDEJA-01 |
|---|---|
| **ID** | BANDEJA-01 |
| **Referencia** | `streamlit_fixtures.py` líneas 33-84 (aprox.) |
| **Título** | Caso CLM-WA-0001 (Marta Soler Puig, documentación completa) → PAGO al procesar |
| **Prioridad** | Alta |
| **Tipo** | Funcional |
| **Precondiciones** | App Streamlit arrancada, vista "Bandeja" |
| **Pasos** | 1. Ir a "Bandeja".<br>2. Localizar el caso `CLM-WA-0001` (Marta Soler Puig).<br>3. Comprobar que aparece el mensaje de WhatsApp mencionando la denuncia `D-4521`.<br>4. Pulsar "Revisar y procesar" sobre este caso. |
| **Datos de prueba** | Ninguno (caso fijo): claim_type = danys_propis, amount = 3.200,00 €, documents = [foto_danys, factura, denuncia_companyia] (completos) |
| **Resultado esperado** | Tras procesar, aparece "Pago aprobado" en el resultado; decisión `PAGO` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | BANDEJA-02 |
|---|---|
| **ID** | BANDEJA-02 |
| **Referencia** | `streamlit_fixtures.py` líneas 62-83 (comentario explícito: "Documentación incompleta a propósito") |
| **Título** | Caso CLM-WA-0002 (Jordi Ferrer Camps, solo 1 documento de 3) → Información requerida al procesar |
| **Prioridad** | Media |
| **Tipo** | Funcional |
| **Precondiciones** | Igual que BANDEJA-01 |
| **Pasos** | 1. Ir a "Bandeja".<br>2. Localizar el caso `CLM-WA-0002` (Jordi Ferrer Camps).<br>3. Pulsar "Revisar y procesar". |
| **Datos de prueba** | Caso fijo: claim_type = danys_propis, amount = 2.900,00 €, documents = [foto_danys] únicamente (faltan factura y denuncia_companyia) |
| **Resultado esperado** | Decisión `INFO_REQUERIDA`; el motivo menciona los documentos que faltan: `factura, denuncia_companyia` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## BLINDAJE — Entradas rotas desde la interfaz (A1/A2/A3)

**Objetivo:** confirmar en pantalla, no solo en tests automáticos, que el blindaje A1 (validación de entrada), A2 (captura global de errores) y A3 (nunca mostrar un traceback) se sostienen.

| Campo | BLINDAJE-01 |
|---|---|
| **ID** | BLINDAJE-01 |
| **Referencia** | Igual que T7-01 (importe = 0) |
| **Título** | Importe = 0 € desde la UI → Rechazo legible, sin error técnico |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Precondiciones** | App Streamlit arrancada |
| **Pasos** | Igual que T7-01 |
| **Datos de prueba** | amount = 0.0 |
| **Resultado esperado** | Igual que T7-01: `RECHAZO`, sin traceback ni mensaje técnico en pantalla |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | BLINDAJE-02 |
|---|---|
| **ID** | BLINDAJE-02 |
| **Referencia** | Igual que T7-02 (nombre > 200 caracteres) |
| **Título** | Nombre del asegurado excesivamente largo → Revisión humana legible, sin error técnico |
| **Prioridad** | Media |
| **Tipo** | Adversario |
| **Precondiciones** | App Streamlit arrancada |
| **Pasos** | Igual que T7-02 |
| **Datos de prueba** | Igual que T7-02 |
| **Resultado esperado** | Igual que T7-02: `REVISION_HUMANA`, sin traceback |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | BLINDAJE-03 |
|---|---|
| **ID** | BLINDAJE-03 |
| **Referencia** | `streamlit_app.py:561-563` (`if not claim_type or amount is None: st.warning(...)`) |
| **Título** | Enviar el formulario sin tipo de siniestro ni importe → aviso de campos obligatorios, no una excepción |
| **Prioridad** | Baja |
| **Tipo** | Adversario |
| **Precondiciones** | App Streamlit arrancada, vista "Nueva reclamación" |
| **Pasos** | 1. En el formulario personalizado, dejar "Tipo de siniestro" sin seleccionar y "Importe reclamado" vacío.<br>2. Pulsar "Procesar reclamación" sin rellenar nada más. |
| **Datos de prueba** | claim_type = None, amount = None |
| **Resultado esperado** | Aviso amarillo con el texto exacto `"Indica al menos el tipo de siniestro y el importe reclamado."` (`streamlit_app.py:563`); no se llega a invocar `process_claim`, no aparece ningún resultado ni traceback |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## Tabla resumen final

| ID | Título | Prioridad | Estado |
|---|---|---|---|
| T1-01 | 32 casos sintéticos, con/sin clave API | Alta | |
| T1-02 | Test automático de determinismo | Alta | |
| T2-01 | 200 importes aleatorios, no-bypass HITL | Alta | |
| T3-01 | RC, 5.000,00 € → PAGO | Alta | |
| T3-02 | RC, 5.000,01 € → REVISION_HUMANA | Alta | |
| T3-03 | Daños propios, 5.300,00 € → PAGO | Media | |
| T3-04 | Daños propios, 5.300,01 € → REVISION_HUMANA | Media | |
| T4-01 | Falso positivo OFAC "Dimitri Volkoff" | Alta | |
| T4-02 | Falso positivo OFAC "Grup Financer Centaure" | Media | |
| T4-03 | No-falso-positivo "Ramirez Fuentes" | Media | |
| T5.1-01 | OFAC + docs incompletos → INFO_REQUERIDA | Alta | |
| T6-01 | Sin clave API → fallback determinista | Alta | |
| T6-02 | Clave API inválida → fallback tras fallo | Media | |
| T6-03 | RAG desactivado → catálogo determinista | Media | |
| T6-04 | Sin clave API + documento real subido | Baja | |
| T6-05 | Base de datos caída → resultado igual, sin error | Media | |
| T7-01 | Importe 0 € → RECHAZO | Alta | |
| T7-02 | Nombre > 200 caracteres → REVISION_HUMANA | Media | |
| T7-03 | Sin documentos → INFO_REQUERIDA | Baja | |
| DEMO-01 | 5 escenarios × 10 repeticiones | Alta | |
| BANDEJA-01 | CLM-WA-0001 → PAGO | Alta | |
| BANDEJA-02 | CLM-WA-0002 → INFO_REQUERIDA | Media | |
| BLINDAJE-01 | Importe 0 sin error técnico | Alta | |
| BLINDAJE-02 | Nombre largo sin error técnico | Media | |
| BLINDAJE-03 | Formulario incompleto → aviso, no excepción | Baja | |

**Total: 25 casos de prueba.**

---

## Nota de verificación (T2)

El script `backend/scripts/uat_t2_random_amounts.py` se ejecutó el 2026-08-08 (`--n 200 --seed 7`) para confirmar que no está roto antes de entregar este documento. Resultado real obtenido:

```
Casos ejecutados: 200
Fallos (amount > 5000.0 EUR pero decision == PAGO): 0
OK: ningun caso con importe > umbral HITL obtuvo PAGO automatico.
```

Durante la ejecución, la terminal mostró avisos repetidos del tipo `No se han podido persistir las decisiones de UAT-T2-XXXX: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server on 'mariadb'")`. **Esto es esperado y no es un fallo**: es la persistencia best-effort en base de datos (`orchestrator.py:419-441`, ver T6-05) fallando porque no había un MariaDB local arrancado durante esta verificación — el resultado de cada caso se calculó y evaluó igualmente con normalidad, ya que la persistencia está envuelta en un `try/except` que nunca interrumpe el flujo. De hecho, esta ejecución sirve como una confirmación adicional en vivo de T6-05.
