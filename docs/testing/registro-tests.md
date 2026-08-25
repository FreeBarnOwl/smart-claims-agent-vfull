# Registro de pruebas — Smart-Claims Agent

Documento de registro de las pruebas realizadas sobre el prototipo Smart-Claims Agent para el Trabajo Final de Máster. Recoge **qué se ha probado, cómo y con qué resultado**, en tres niveles complementarios:

| Nivel | Qué es | Volumen | Resultado |
|---|---|---|---|
| **1. Suite automatizada (pytest)** | Tests unitarios, de integración y end-to-end que se ejecutan sin red, sin Docker y sin MariaDB | **100 tests** en 14 ficheros | **100/100 en verde** (ejecución del 2026-08-25) |
| **2. Evaluación sobre dataset sintético** | Scripts que procesan lotes de expedientes y comparan la decisión con la esperada | 32 casos + 200 importes aleatorios + 6 documentos Vision | 32/32 · 200/200 · 17/17 campos |
| **3. Pruebas de aceptación de usuario (UAT)** | Guiones manuales para que una persona ajena al desarrollo ataque el sistema desde la interfaz | 31 casos de prueba | 1 ejecutado y verificado (T2-01); resto pendiente de la sesión UAT |

Última ejecución completa de la suite automatizada:

```
Fecha:      2026-08-25
Commit:     fd38de3 (rama main)
Entorno:    Windows 11 · Python 3.11.5 · pytest 9.0.3 · pytest-asyncio 1.3.0
Comando:    py -3.11 -m pytest tests/ -v          (desde backend/, con ANTHROPIC_API_KEY vacía)
Resultado:  ======================= 100 passed in 365.22s (0:06:05) =======================
```

---

## 1. Suite automatizada (pytest)

### 1.1 Infraestructura de pruebas

Los tests viven en [`backend/tests/`](../../backend/tests/) y se configuran en [`backend/pytest.ini`](../../backend/pytest.ini) (`asyncio_mode = auto`, descubrimiento `test_*.py`). Los principios de diseño de la suite son:

- **Sin dependencias externas.** La fixture `test_db` de [`conftest.py`](../../backend/tests/conftest.py) sustituye la sesión de producción (aiomysql/MariaDB) por **SQLite asíncrono en memoria**; cada test arranca con un esquema limpio. No hace falta Docker.
- **Sin LLM.** Sin `ANTHROPIC_API_KEY`, el helper `reason()` y el módulo de visión usan su **fallback determinista**, por lo que los tests son reproducibles y no consumen API. Cuando un test necesita verificar el comportamiento *con* LLM (timeouts, contenido adversarial), lo simula con `monkeypatch`, incluyendo excepciones reales del SDK (`anthropic.APITimeoutError`).
- **UI probada en headless.** La app Streamlit se ejecuta con `streamlit.testing.v1.AppTest`, sin navegador.
- **RAG real en test.** Los tests de RAG usan el ChromaDB embebido con las pólizas sintéticas del repositorio; son los más lentos de la suite por la carga del modelo de embeddings.

> **Nota operativa.** Si existe un fichero `.env` con `ANTHROPIC_API_KEY` en la raíz del repositorio, `load_dotenv()` la carga y los tests pasan a llamar a la API real (siguen pasando, pero tardan mucho más y consumen crédito). Para la ejecución de referencia se lanzó la suite con la variable definida y vacía (`ANTHROPIC_API_KEY=""`), que tiene prioridad sobre el `.env`.

### 1.2 Resumen por fichero

| Fichero | Componente bajo prueba | Tests | Resultado |
|---|---|---|---|
| `test_agents.py` | Agentes B, C, D, G y E (aislados) | 12 | ✅ 12/12 |
| `test_api.py` | API REST FastAPI (`POST /claims`, `GET /claims/{id}`) | 4 | ✅ 4/4 |
| `test_bandeja_fixtures.py` | Fixtures de la vista "Bandeja" (adjuntos, miniaturas) | 2 | ✅ 2/2 |
| `test_conciliation_advisor.py` | Agente F — asistente de conciliación por reglas | 22 | ✅ 22/22 |
| `test_determinism.py` | Núcleo de decisión inmune al contenido del LLM | 1 | ✅ 1/1 |
| `test_fraud_coherence.py` | 4.º detector del Agente G (coherencia documental) en el flujo | 2 | ✅ 2/2 |
| `test_fraud_tools.py` | Motor antifraude: OFAC, Z-score, duplicados, coherencia, score | 15 | ✅ 15/15 |
| `test_input_validation.py` | Blindaje A1 — `validate_claim_input()` | 13 | ✅ 13/13 |
| `test_orchestration.py` | Flujo completo A→B→C→G→D→E y blindajes A1/A2/A4 | 10 | ✅ 10/10 |
| `test_rag.py` | RAG de pólizas (ChromaDB) y fallback al catálogo | 3 | ✅ 3/3 |
| `test_reasoning.py` | Helper `reason()`: fallback, timeout | 4 | ✅ 4/4 |
| `test_repository.py` | Capa de persistencia | 5 | ✅ 5/5 |
| `test_streamlit_ui.py` | UI Streamlit (AppTest): demo, Bandeja, Caso libre, Conciliación | 4 | ✅ 4/4 |
| `test_vision.py` | Extracción multimodal (`vision.py`): fallback, timeout | 3 | ✅ 3/3 |
| **Total** | | **100** | **✅ 100/100** |

### 1.3 Detalle de los casos de prueba

Cada línea indica el test y la propiedad que verifica.

#### `test_agents.py` — agentes especialistas (12)

| Test | Verifica |
|---|---|
| `test_agent_b_validates_complete_docs` | Agente B acepta un expediente con la documentación completa |
| `test_agent_b_detects_missing_docs` | Agente B detecta documentos que faltan según el tipo de siniestro |
| `test_agent_b_unknown_type_uses_default` | Tipo de siniestro desconocido → lista de documentos por defecto |
| `test_agent_g_clear_when_no_signals` | Agente G devuelve `CLEAR` sin señales de fraude |
| `test_agent_g_blocks_ofac_match` | Coincidencia OFAC → veredicto `BLOCKED` |
| `test_agent_g_high_risk_on_extreme_amount` | Importe extremo → `HIGH_RISK` |
| `test_agent_c_extracts_with_confidence` | Agente C devuelve campos extraídos con nivel de confianza |
| `test_agent_d_covers_danys_propis` | Agente D confirma cobertura para "daños propios" |
| `test_agent_d_no_coverage_for_mechanical` | Agente D niega cobertura para avería mecánica |
| `test_agent_e_approves_payment_low_amount` | Agente E aprueba `PAGO` por debajo del umbral HITL |
| `test_agent_e_routes_hitl_high_amount` | Agente E deriva a `REVISION_HUMANA` por encima del umbral |
| `test_agent_e_rejects_no_coverage` | Agente E emite `RECHAZO` sin cobertura |

#### `test_api.py` — API REST (4)

| Test | Verifica |
|---|---|
| `test_create_claim_returns_decision` | `POST /claims` procesa el expediente y devuelve la decisión |
| `test_get_claim_after_processing` | `GET /claims/{id}` recupera el expediente persistido |
| `test_get_claim_not_found_returns_404` | Id inexistente → 404 |
| `test_create_claim_internal_error_does_not_leak_exception_detail` | Blindaje A3: un error interno no filtra traceback ni excepción cruda al cliente |

#### `test_bandeja_fixtures.py` — vista Bandeja (2)

| Test | Verifica |
|---|---|
| `test_all_attachment_files_exist_on_disk` | Todos los adjuntos referenciados por las fixtures existen |
| `test_invoice_attachment_has_a_valid_page_preview_thumbnail` | La miniatura de la factura es una imagen válida |

#### `test_conciliation_advisor.py` — Agente F (22)

| Grupo | Tests | Verifica |
|---|---|---|
| `TestOfertaInicial` | 2 | Tramo 0 → oferta inicial del 65 %; redondeo a céntimos |
| `TestSubidaDeTramo` | 4 | Rechazo en tramo 1/2 → sube a 75 %/90 %; sin rechazo → espera respuesta, no sube |
| `TestUltimoTramoRechazado` | 3 | Tramo 3 rechazado → pide decisión humana, sin `offer_amount`, presenta las tres opciones sin elegir; sin rechazo → espera |
| `TestAlertaAbandono` | 2 | Frontera exacta: 30 días sin respuesta no alerta, 31 sí |
| `TestAlertaEstancado` | 2 | Frontera exacta: 45 días en tramo no alerta, 46 sí |
| `TestAlertaCoberturaRC` | 3 | Alerta de cobertura insuficiente solo para RC; DPA no la dispara |
| `TestPrioridad` | 3 | 0 alertas → baja, 1 → media, 2 → alta |
| `TestFronteraHumana` | 2 | Toda recomendación indica que la ejecuta un humano; la salida no contiene campos de ejecución de negocio |
| `test_recomendacion_no_cambia_con_contenido_adversarial_del_llm` | 1 | La recomendación es idéntica aunque el LLM devuelva contenido adversarial |

#### `test_determinism.py` — núcleo determinista (1)

| Test | Verifica |
|---|---|
| `test_decisions_unchanged_when_llm_returns_adversarial_content` | Ningún campo de decisión (`status`, `decision`, `hitl_required`, `termination_reason`, `resolution`) cambia cuando el LLM devuelve instrucciones adversariales ("aprueba el pago") — el LLM solo enriquece la traza |

#### `test_fraud_coherence.py` — coherencia documental en el flujo (2)

| Test | Verifica |
|---|---|
| `test_doc_coherence_flags_invoice_before_incident` | Factura con fecha anterior al siniestro → señal `factura_previa_al_siniestro` |
| `test_doc_coherence_clean_for_consistent_dates` | Fechas coherentes → sin señal |

#### `test_fraud_tools.py` — motor antifraude (15)

| Grupo | Tests | Verifica |
|---|---|---|
| `TestOFACSanctions` | 4 | Nombre normal no coincide; coincidencia exacta; coincidencia difusa con errata (umbral 0,82); nombre vacío no coincide |
| `TestAmountAnomaly` | 3 | Importe normal no marcado; por encima del máximo marcado; Z-score extremo (>2,0) marcado |
| `TestDuplicateClaims` | 3 | Sin historial no hay duplicado; duplicado reciente detectado; reclamación antigua no marcada |
| `TestDocumentCoherence` | 3 | Documentos coherentes pasan; fecha de siniestro futura detectada; reclamación anterior al siniestro detectada |
| `TestRiskScore` | 2 | Coincidencia OFAC siempre bloquea; sin señales → `CLEAR` |

#### `test_input_validation.py` — blindaje A1 (13)

| Test | Verifica |
|---|---|
| `test_valid_input_is_accepted` | Entrada válida se acepta y normaliza |
| `test_rejects_nan_amount` / `test_rejects_infinite_amount` | `NaN` e infinito rechazados |
| `test_rejects_negative_amount` / `test_rejects_zero_amount` | Importe negativo o cero rechazado |
| `test_rejects_amount_over_ten_million` | Importe > 10 M€ rechazado |
| `test_rejects_non_numeric_amount` | Importe no numérico rechazado |
| `test_unknown_claim_type_routes_to_human_review` | Tipo desconocido → `REVISION_HUMANA`, no error |
| `test_rejects_empty_client_name` / `test_rejects_whitespace_only_client_name` | Nombre vacío o solo espacios rechazado |
| `test_rejects_client_name_over_200_chars` | Nombre > 200 caracteres rechazado |
| `test_normalizes_client_name_whitespace` | Espacios múltiples normalizados |
| `test_deduplicates_documents` | Documentos repetidos deduplicados |

#### `test_orchestration.py` — flujo end-to-end (10)

| Test | Verifica |
|---|---|
| `test_flow_automatic_payment` | Escenario 1: docs completos + importe bajo → `resolved` / `PAGO` |
| `test_flow_hitl_high_amount` | Escenario 2: importe alto → `pending_review` / `REVISION_HUMANA` |
| `test_flow_rejection_no_coverage` | Escenario 3: sin cobertura → `rejected` / `RECHAZO` |
| `test_flow_request_info_missing_docs` | Escenario 4: faltan documentos → `validating` / `INFO_REQUERIDA` |
| `test_process_claim_handles_internal_error_gracefully` | Blindaje A2: `process_claim` nunca propaga excepciones internas |
| `test_invalid_amount_is_rejected_without_calling_specialist_agents` | Importe inválido se rechaza en triage, sin ejecutar B–E |
| `test_unknown_claim_type_routes_to_human_review_without_specialists` | Tipo desconocido va a revisión humana sin ejecutar especialistas |
| `test_duplicate_documents_are_deduplicated_before_validation` | La deduplicación ocurre antes del Agente B |
| `test_flow_completes_with_decision_when_llm_times_out_for_real` | Blindaje A4: con `anthropic.APITimeoutError` real el flujo termina con decisión |
| `test_decisions_log_accumulates` | El log de decisiones acumula una entrada por agente |

#### `test_rag.py` — RAG de pólizas (3)

| Test | Verifica |
|---|---|
| `test_retrieve_policy_matches_each_type` | La recuperación devuelve la póliza correcta para cada tipo de siniestro (4/4) |
| `test_agent_d_uses_rag_and_computes_coverage` | Agente D usa el resultado del RAG (`source == "rag"`) y calcula la cobertura |
| `test_agent_d_fallback_to_mock_when_rag_disabled` | Con `SCA_RAG_ENABLED=0` el Agente D usa el catálogo determinista |

#### `test_reasoning.py` — helper `reason()` (4)

| Test | Verifica |
|---|---|
| `test_reason_uses_fallback_when_no_api_key` | Sin clave API → fallback determinista |
| `test_reason_falls_back_on_exception` | Excepción del cliente → fallback, sin propagar |
| `test_reason_configures_llm_timeout` | El cliente Anthropic se crea con `timeout=20 s` |
| `test_reason_falls_back_on_real_api_timeout_error` | `anthropic.APITimeoutError` real → fallback |

#### `test_repository.py` — persistencia (5)

| Test | Verifica |
|---|---|
| `test_save_claim_creates_new` | Inserta un expediente nuevo |
| `test_save_claim_idempotent` | Guardar dos veces el mismo id no duplica |
| `test_log_agent_decision_persists` | Las decisiones de agente se persisten |
| `test_get_claim_not_found` | Id inexistente → `None` |
| `test_list_claims_paginates` | Listado paginado |

#### `test_streamlit_ui.py` — interfaz Streamlit (4)

| Test | Verifica |
|---|---|
| `test_streamlit_demo_scenario_never_shows_raw_traceback` | Blindaje A3: ante un fallo interno la UI muestra un aviso, nunca el traceback |
| `test_bandeja_view_shows_fixture_cases_and_processes_pago_automatico` | La vista Bandeja lista los casos y procesa `CLM-WA-0001` → `PAGO` |
| `test_caso_libre_view_lets_broken_amount_trigger_blindaje_a1` | El panel "Caso libre" con importe roto activa el blindaje A1 |
| `test_conciliacion_view_shows_fixture_recommendations` | La vista Conciliación muestra las recomendaciones del Agente F |

#### `test_vision.py` — extracción multimodal (3)

| Test | Verifica |
|---|---|
| `test_analyze_document_returns_none_without_api_key` | Sin clave → `None` (el Agente C usa su extracción por defecto) |
| `test_analyze_document_configures_timeout` | El cliente se crea con `timeout=20 s` |
| `test_analyze_document_falls_back_on_real_api_timeout_error` | `APITimeoutError` real → `None`, sin propagar |

### 1.4 Tiempos de ejecución

Los diez tests más lentos de la ejecución de referencia (el resto tarda menos de 12 s cada uno; la mayoría, milisegundos):

| Duración | Test | Motivo |
|---|---|---|
| 96,6 s | `test_api.py::test_create_claim_returns_decision` | Primer arranque de la app + carga de ChromaDB y modelo de embeddings |
| 83,8 s | `test_api.py::test_get_claim_after_processing` | Ídem (flujo completo con RAG) |
| 39,5 s | `test_determinism.py::test_decisions_unchanged_when_llm_returns_adversarial_content` | Flujo completo ×2 (con y sin LLM simulado) |
| 18,3 s | `test_conciliation_advisor.py::TestSubidaDeTramo::test_stage_1_rechazada_sube_a_75_por_ciento` | Import inicial del módulo |
| 17,5 s | `test_streamlit_ui.py::test_streamlit_demo_scenario_never_shows_raw_traceback` | AppTest ejecuta el script Streamlit completo |
| 15,8 s | `test_conciliation_advisor.py::TestOfertaInicial::test_stage_0_recomienda_oferta_inicial_65_por_ciento` | |
| 15,5 s | `test_conciliation_advisor.py::TestOfertaInicial::test_oferta_inicial_redondea_a_centimos` | |
| 15,4 s | `test_streamlit_ui.py::test_bandeja_view_shows_fixture_cases_and_processes_pago_automatico` | AppTest + flujo completo |
| 14,5 s | `test_conciliation_advisor.py::TestSubidaDeTramo::test_stage_2_rechazada_sube_a_90_por_ciento` | |
| 12,1 s | `test_conciliation_advisor.py::TestSubidaDeTramo::test_stage_1_sin_rechazo_espera_respuesta_no_sube_tramo` | |

### 1.5 Evolución de la suite

| Hito | Tests | Fuente |
|---|---|---|
| Prototipo E2E inicial (Entrega 2, junio 2026) | 25 | [BITÁCORA](../BITACORA.md), fase de evaluación |
| Motor antifraude determinista (4 detectores) | 42 (+15 `test_fraud_tools.py`; +2 `test_fraud_coherence.py`) | BITÁCORA, fases 8 y 10 |
| RAG real de pólizas | 47 (+3 `test_rag.py`) | BITÁCORA, fase 9 |
| Blindajes A1–A4, determinismo, API, UI Streamlit, Bandeja | 78 | commits `1c396ee`, `28f7962`, `67f3c6a`, `db518d2`, `4180ae1`, `6b61149`, `a5814f7` |
| Agente F (asistente de conciliación) | 100 (+22 `test_conciliation_advisor.py`) | BITÁCORA, fase 12 |

---

## 2. Evaluación sobre dataset sintético

Pruebas de lote que ejecutan el flujo completo sobre expedientes generados y comparan la decisión obtenida con la esperada. El detalle metodológico y la matriz de confusión están en el capítulo [4. Evaluación y resultados](../memoria/04-evaluacion.md) de la memoria.

| Prueba | Script | Casos | Resultado |
|---|---|---|---|
| Precisión del flujo de decisión | [`backend/scripts/evaluate_inprocess.py`](../../backend/scripts/evaluate_inprocess.py) (in-process, sin servidor ni MariaDB) | 32 expedientes sintéticos, 5 escenarios (PAGO / RECHAZO / REVISION_HUMANA / INFO_REQUERIDA / RECHAZO_FRAUDE, incl. OFAC) | **32/32 (100 %)**, matriz de confusión diagonal |
| No-bypass del control humano (UAT T2) | [`backend/scripts/uat_t2_random_amounts.py`](../../backend/scripts/uat_t2_random_amounts.py) (`--n 200 --seed 7`, ejecutado el 2026-08-08) | 200 reclamaciones RC con importe aleatorio 1–100.000 € | **0 fallos**: ningún caso con importe > 5.000 € obtuvo `PAGO` automático |
| Extracción multimodal real (Agente C, Claude Vision) | Evaluación manual con *ground truth* | 6 documentos sintéticos (facturas, acta policial, informe de taller) | **17/17 campos** (tipo 6/6, importe 5/5, fecha 6/6) |

---

## 3. Pruebas de aceptación de usuario (UAT)

Los guiones están en [`uat_scripts.md`](uat_scripts.md) (regenerados el 2026-08-09). Están pensados para una "sesión de ataque dirigido" ejecutada por una persona que no ha participado en el desarrollo, y cada resultado esperado cita la constante o línea de código de la que procede.

| Bloque | Casos | Qué ataca |
|---|---|---|
| T1 — Determinismo del LLM | 2 | Mismo resultado con y sin clave API; test automático de determinismo |
| T2 — No-bypass HITL | 1 | 200 importes aleatorios (ver §2) |
| T3 — Fronteras del umbral HITL | 5 | 4.999,99 / 5.000,00 / 5.000,01 €; efecto de la franquicia (5.300 €) |
| T4 — Falsos positivos OFAC | 3 | Nombres parecidos a sancionados; nombre con acentos |
| T5.1 — Orden de compuertas | 1 | OFAC + documentación incompleta |
| T6 — Degradación de servicios | 5 | Sin clave API, clave inválida, RAG desactivado, documento real sin clave, base de datos caída |
| T7 — Entradas adversarias | 5 | Importe 0, nombre > 200 caracteres, sin documentos, inyección SQL, unicode |
| LIBRE — Panel "Caso libre" (A5) | 3 | Caso feliz, caso roto, formulario vacío |
| DEMO — Escenarios de demostración | 1 | 5 escenarios × 10 repeticiones |
| BANDEJA — Vista Bandeja | 2 | `CLM-WA-0001` → PAGO; `CLM-WA-0002` → INFO_REQUERIDA |
| BLINDAJE — Entradas rotas desde la UI | 3 | Importe 0, nombre largo, formulario incompleto: aviso, nunca excepción |
| **Total** | **31** | |

**Estado:** T2-01 ejecutado y verificado el 2026-08-08 (resultado registrado en el propio guion). Los 30 casos restantes tienen la casilla "Resultado obtenido" en blanco a la espera de la sesión UAT; muchos de ellos tienen además su equivalente automatizado en la suite pytest (T1-02 ↔ `test_determinism.py`; T6-01/02 ↔ `test_reasoning.py`; T6-03 ↔ `test_rag.py`; T7-01/02 y BLINDAJE ↔ `test_input_validation.py` y `test_streamlit_ui.py`; BANDEJA-01 ↔ `test_streamlit_ui.py`).

---

## 4. Cómo reproducir la ejecución

```bash
cd backend
# Sin clave API: modo determinista, ~6 min (la mayor parte es la carga de ChromaDB/embeddings)
ANTHROPIC_API_KEY="" py -3.11 -m pytest tests/ -v            # Windows (launcher py)
ANTHROPIC_API_KEY="" python -m pytest tests/ -v              # Linux/macOS

# Solo la parte rápida (sin UI Streamlit ni RAG)
ANTHROPIC_API_KEY="" python -m pytest tests/ -v --ignore=tests/test_streamlit_ui.py --ignore=tests/test_rag.py

# Con Docker (backend levantado)
docker exec -it sca-backend pytest tests/ -v

# Evaluación sobre el dataset sintético y UAT T2
py scripts/evaluate_inprocess.py
py scripts/uat_t2_random_amounts.py --n 200 --seed 7
```

Requisitos: Python 3.11 y las dependencias de `backend/requirements.txt`. No hace falta MariaDB, Docker ni clave de Anthropic.

---

## 5. Limitaciones y trabajo pendiente

- **No hay integración continua para los tests.** El único workflow de GitHub Actions ([`dependency-audit.yml`](../../.github/workflows/dependency-audit.yml)) audita dependencias; no ejecuta pytest, por lo que el historial de ejecuciones se documenta aquí manualmente. Añadir un workflow `tests.yml` que ejecute la suite en cada push dejaría el registro en la pestaña *Actions*.
- **No se mide cobertura de código.** La suite cubre los caminos de decisión y los blindajes, pero no se ha generado un informe `--cov`.
- **Los tests no ejercitan el LLM real.** Por diseño, verifican que la decisión es independiente del LLM y que los fallos de la API degradan correctamente; la calidad del razonamiento generado por Claude se valida cualitativamente en las demostraciones y en la evaluación del Agente C (§2).
- **UAT parcialmente ejecutada.** 30 de los 31 casos manuales están pendientes de la sesión con la usuaria de negocio.
