# Guiones de prueba UAT — Smart-Claims Agent

Guiones de prueba de aceptación de usuario (UAT) para que Miriam ejecute la "sesión de ataque dirigido" del 2026-08-13 sobre el prototipo. Cubren determinismo del LLM, no-bypass del control humano, umbrales exactos, falsos positivos OFAC, orden de las compuertas, degradación de servicios, entradas adversarias (incluida inyección SQL y unicode), los 5 escenarios de demo, la vista Bandeja, el blindaje de entrada y el panel "Caso libre".

**Regenerado por completo el 2026-08-09** con un nivel de detalle nuevo: cada caso es autocontenido y ejecutable por alguien que no ha visto nunca la aplicación, sin remisiones a otros casos ni precondiciones implícitas. Sustituye a la versión anterior (25 casos, commit `c9d455f`).

## REGLA DE ORO

**Todo "Resultado esperado" de este documento viene de una constante, cadena de texto o ruta de código real, citada con su archivo y línea.** Nada se ha inventado ni redondeado. Si un valor no se pudo verificar directamente en el código, se marca `[VERIFICAR]` en vez de adivinarlo. Si algo cambia en el código después de esta fecha (2026-08-09), este documento puede quedar desactualizado — reconfirma contra el código antes de una sesión de pruebas si ha pasado tiempo.

Fuentes citadas en todo el documento:
- `backend/app/agents/orchestrator.py` (Agente A — supervisor, `validate_claim_input`, `supervisor_router`, `_normalize_final_state`, `process_claim`)
- `backend/app/agents/document_validator.py` (Agente B)
- `backend/app/agents/multimodal_extractor.py` + `backend/app/agents/vision.py` (Agente C)
- `backend/app/tools/fraud_tools.py` (Agente G — `check_ofac_sanctions`, `compute_risk_score`)
- `backend/app/agents/coverage_checker.py` + `backend/app/tools/claim_tools.py::check_policy` (Agente D)
- `backend/app/agents/claim_resolver.py` (Agente E)
- `backend/app/agents/reasoning.py` (helper `reason()`, LLM opcional)
- `backend/app/db/repository.py` (persistencia — `save_claim`, `log_agent_decision`)
- `streamlit_app.py`, `streamlit_fixtures.py`
- `backend/tests/test_determinism.py`, `backend/tests/test_streamlit_ui.py`, `backend/scripts/evaluate_inprocess.py`, `backend/scripts/uat_t2_random_amounts.py`
- `README.md`, `.env.example`

## Formato de cada caso de prueba

Cada caso de prueba de este documento sigue esta ficha:

| Campo | Contenido |
|---|---|
| **ID** | Identificador único del caso (p. ej. `T3-01`) |
| **Referencia** | Archivo:línea del código que sustenta el resultado esperado |
| **Título** | Descripción corta de qué se prueba |
| **Prioridad** | Alta / Media / Baja |
| **Tipo** | Funcional / Regresión / Frontera / Adversario / Degradación |
| **Entorno** | Uno de: `Cloud — navegador` (se usa la app desplegada, sin tocar nada del ordenador) · `Local — terminal` (se ejecutan scripts/tests desde una terminal, sin arrancar la interfaz web) · `Local — app con entorno modificado` (se arranca la app Streamlit en el propio ordenador con alguna variable de entorno cambiada a propósito) |
| **Precondiciones** | Estado necesario antes de empezar |
| **Pasos** | Pasos numerados, completos y autocontenidos — no remiten a otro caso |
| **Datos de prueba** | Valores exactos a introducir |
| **Resultado esperado** | Qué debe verse, citando la constante/cadena real |
| **Resultado obtenido** | _(a rellenar por Miriam durante la ejecución)_ |
| **Estado** | _(a rellenar: OK / KO / Bloqueado)_ |
| **Evidencia** | _(a rellenar: captura de pantalla o ruta de log)_ |

**Nota sobre el formato numérico en pantalla:** la app formatea los importes pagados/solicitados con `f"{valor:,.0f} €"` (`streamlit_app.py:365-368`), que es formato Python **sin configuración regional** — usa la **coma** como separador de miles (p. ej. `5,000 €`, no `5.000 €` a la española). Todos los "Resultado esperado" de este documento citan el importe tal como lo escribe realmente el código. En el texto explicativo de este documento (fuera de las cadenas literales de pantalla) sí se usan puntos como separador de miles, a la española, por legibilidad.

---

## T1 — Determinismo del razonamiento LLM

**Objetivo:** demostrar que quitar o poner la clave de Anthropic **nunca cambia una decisión**, solo el texto del razonamiento. Es el diseño "núcleo determinista + LLM opcional" (`reason()`, `backend/app/agents/reasoning.py:24-56`): sin `ANTHROPIC_API_KEY`, `reason()` devuelve el `fallback` determinista al instante (línea 38: `if not os.getenv("ANTHROPIC_API_KEY"): return fallback`); con clave, invoca a Claude (timeout 20s, línea 44: `ChatAnthropic(model=MODEL, max_tokens=1024, temperature=0, timeout=20)`) pero **nunca** decide campos como `decision`, `status` o `hitl_required`.

| Campo | T1-01 |
|---|---|
| **ID** | T1-01 |
| **Referencia** | `backend/scripts/evaluate_inprocess.py:54-95` (32 casos sintéticos), `backend/tests/test_determinism.py:16-20,97-119` |
| **Título** | Las 32 decisiones del dataset sintético no cambian con/sin clave de API |
| **Prioridad** | Alta |
| **Tipo** | Regresión |
| **Entorno** | Local — terminal |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador, en una carpeta local (por ejemplo `C:\proyectos\smart-claims-agent-vfull`), y Python 3.11 instalado (comprobable con `py --version` en una terminal). |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta del proyecto: `cd C:\proyectos\smart-claims-agent-vfull` (sustituye la ruta por la real en tu ordenador).<br>3. Entra en la carpeta `backend`: `cd backend`.<br>4. Instala las dependencias: `py -m pip install -r requirements.txt`.<br>5. Asegúrate de que no hay clave definida en esta sesión de terminal: `Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue`.<br>6. Ejecuta `py scripts/evaluate_inprocess.py`.<br>7. Abre el fichero de salida `data/synthetic/evaluation_inprocess.json` (por ejemplo con `notepad data/synthetic/evaluation_inprocess.json`) y copia/anota el campo `decision` de cada uno de los 32 casos.<br>8. Guarda ese fichero con otro nombre para no perderlo, por ejemplo `Copy-Item data/synthetic/evaluation_inprocess.json data/synthetic/evaluation_sin_clave.json`.<br>9. Ahora define una clave real de Anthropic solo para esta sesión de terminal: `$env:ANTHROPIC_API_KEY = "sk-ant-api03-TU_CLAVE_REAL"` (sustituye por una clave válida de verdad).<br>10. Repite el paso 6: `py scripts/evaluate_inprocess.py`.<br>11. Copia el nuevo resultado: `Copy-Item data/synthetic/evaluation_inprocess.json data/synthetic/evaluation_con_clave.json`.<br>12. Compara los campos `decision` de ambos ficheros (`evaluation_sin_clave.json` vs `evaluation_con_clave.json`), caso a caso, por ejemplo abriendo ambos en el editor y comparando visualmente, o con `Compare-Object (Get-Content data/synthetic/evaluation_sin_clave.json) (Get-Content data/synthetic/evaluation_con_clave.json)` (esto también mostrará diferencias de texto en el razonamiento, que sí es normal que cambien). |
| **Datos de prueba** | El dataset lo genera el propio script (`build_cases()`, `evaluate_inprocess.py:54-95`); no requiere datos manuales |
| **Resultado esperado** | Las 32 decisiones (`decision`, `status`, `hitl_required`) coinciden 1:1 entre ambas ejecuciones. Es exactamente la comprobación que describe el docstring de `test_determinism.py:16-20`. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Guardar ambos ficheros JSON de salida (`evaluation_sin_clave.json`, `evaluation_con_clave.json`) como evidencia |

| Campo | T1-02 |
|---|---|
| **ID** | T1-02 |
| **Referencia** | `backend/tests/test_determinism.py::test_decisions_unchanged_when_llm_returns_adversarial_content` (línea 97) |
| **Título** | El test automático de determinismo pasa (contenido adversario del LLM simulado) |
| **Prioridad** | Alta |
| **Tipo** | Regresión |
| **Entorno** | Local — terminal |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador y Python 3.11 instalado. |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta del proyecto: `cd C:\proyectos\smart-claims-agent-vfull` (sustituye por la ruta real).<br>3. Entra en `backend`: `cd backend`.<br>4. Instala las dependencias si no lo has hecho antes: `py -m pip install -r requirements.txt`.<br>5. Ejecuta `py -m pytest tests/test_determinism.py -v`.<br>6. Lee la línea de salida correspondiente al test `test_decisions_unchanged_when_llm_returns_adversarial_content`. |
| **Datos de prueba** | Ninguno (el test genera sus propios casos y simula, con `monkeypatch`, que el LLM devuelve contenido adversario) |
| **Resultado esperado** | El test `test_decisions_unchanged_when_llm_returns_adversarial_content` termina en `PASSED`; internamente comprueba `mismatches == {}` (línea 119) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de la terminal con la línea `PASSED` |

---

## T2 — No-bypass del control humano (umbral HITL) con importes aleatorios

**Objetivo:** ninguna combinación de importe puede saltarse el control humano por encima de 5.000 €. No existía un script para esto — se creó `backend/scripts/uat_t2_random_amounts.py` (única excepción autorizada a "no tocar código de producción", por ser explícitamente una utilidad de prueba, ya presente en el repositorio).

**Nota de diseño del script** (documentada también en su propio docstring): usa el tipo de siniestro `"responsabilitat"` a propósito, porque su franquicia es 0 € (`check_policy`, `backend/app/tools/claim_tools.py:107-140`, regla `"responsabilitat": {"covered": True, "max": 50000, "deductible": 0, "section": "SP-PCS-009 § 4.1"}`). Con franquicia 0, `net_payable == amount` en todo el rango 1-50.000 € (y se capa a 50.000 € por encima) — siempre por encima del umbral HITL de 5.000 €. Con otros tipos (p. ej. `danys_propis`, franquicia 300 €) existe un tramo legítimo (importe entre 5.000 € y 5.300 €) donde la franquicia hace que `net_payable` caiga por debajo del umbral y el sistema aprueba PAGO correctamente — **eso no sería un fallo**, sino la franquicia funcionando como está diseñada. Usar `responsabilitat` aísla la propiedad bajo prueba (el umbral HITL) sin que la franquicia la contamine.

| Campo | T2-01 |
|---|---|
| **ID** | T2-01 |
| **Referencia** | `backend/scripts/uat_t2_random_amounts.py`; umbral en `backend/app/agents/claim_resolver.py:27` (`DEFAULT_HITL_THRESHOLD = 5000.0`), comparación `net_payable > threshold` en línea 108 |
| **Título** | 200 reclamaciones con importe aleatorio (1€-100.000€): ninguna con importe > 5.000 € resulta en PAGO |
| **Prioridad** | Alta |
| **Tipo** | Frontera / Regresión |
| **Entorno** | Local — terminal |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador y Python 3.11 instalado. |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta del proyecto: `cd C:\proyectos\smart-claims-agent-vfull` (sustituye por la ruta real).<br>3. Entra en `backend`: `cd backend`.<br>4. Instala las dependencias si no lo has hecho antes: `py -m pip install -r requirements.txt`.<br>5. Ejecuta `py scripts/uat_t2_random_amounts.py --n 200 --seed 7`.<br>6. Espera a que termine (puede tardar varios minutos; procesa 200 expedientes reales a través de todo el grafo de agentes). Es normal ver avisos en la terminal sobre fallos al conectar con MariaDB (`Can't connect to MySQL server on 'mariadb'`) si no tienes una base de datos local arrancada — esto no es un fallo del caso de prueba, ver T6-05.<br>7. Lee el resumen final impreso en la terminal. |
| **Datos de prueba** | Generados por el propio script: 200 importes aleatorios uniformes entre 1,0 € y 100.000,0 € (semilla fija 7, reproducible) |
| **Resultado esperado** | La línea final dice `OK: ningun caso con importe > umbral HITL obtuvo PAGO automatico.` y `Fallos (amount > 5000.0 EUR pero decision == PAGO): 0` |
| **Resultado obtenido** | Ejecutado el 2026-08-08 durante la redacción de este documento: `Casos ejecutados: 200`, `Fallos (amount > 5000.0 EUR pero decision == PAGO): 0`, `OK: ningun caso con importe > umbral HITL obtuvo PAGO automatico.` (ver nota de verificación al final de este documento) |
| **Estado** | |
| **Evidencia** | Captura de la terminal con el resumen final |

---

## T3 — Fronteras exactas del umbral HITL (5.000 €)

**Objetivo:** probar el borde exacto del umbral en la propia interfaz (`streamlit_app.py`, vista "Nueva reclamación"). La condición real es `net_payable > 5000.0` (estrictamente mayor, `claim_resolver.py:108`) — es decir, exactamente 5.000,00 € de importe neto **sí** paga automáticamente; hace falta superarlo aunque sea en un céntimo para que salte a revisión humana.

**Aviso importante para Miriam:** la app Streamlit activa el RAG real de pólizas por defecto (`os.environ.setdefault("SCA_RAG_ENABLED", "1")`, `streamlit_app.py:38`). Si ChromaDB está disponible, el Agente D puede usar cifras de cobertura/franquicia recuperadas de las pólizas reales en vez de las de la tabla mock de abajo. **Antes de comparar el resultado, comprueba si aparece el bloque "Cobertura (Agente D · RAG sobre pólizas)" en la pantalla de resultado** (`streamlit_app.py:380-387`, solo se muestra si `coverage_result.source == "rag"`): si aparece, anota los valores reales que muestra en "Resultado obtenido" en vez de compararlos ciegamente con esta tabla. Si no aparece ese bloque, se ha usado el catálogo determinista de abajo.

Catálogo determinista de referencia (`backend/app/tools/claim_tools.py:107-140`):

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
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Frontera 5000`.<br>6. En el campo "ID Cliente" escribe: `T3-01`.<br>7. En el campo "Email del cliente" escribe: `t3-01@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Responsabilidad civil`.<br>9. En el campo "Importe reclamado (€)" escribe: `5000`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `acta_policial`, `dades_tercer`.<br>11. No es necesario subir ningún archivo en "Sube los documentos reales...".<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | amount = 5000.00, claim_type = responsabilitat, docs completos |
| **Resultado esperado** | Píldora de decisión = `"Resuelto · Pago aprobado"` (`DECISION_STYLE["PAGO"]`, `streamlit_app.py:99`); tarjeta "Decisión" = `PAGO`; tarjeta "Importe pagado" = `5,000 €` (formato Python con coma, ver nota al principio del documento) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla del resultado |

| Campo | T3-02 |
|---|---|
| **ID** | T3-02 |
| **Referencia** | `claim_resolver.py:108-149` (rama REVISION_HUMANA), cadena exacta en línea 140: `f"importe {net_payable} EUR supera umbral HITL ({threshold} EUR)"` |
| **Título** | Responsabilidad civil, importe 5.000,01 € → Revisión humana |
| **Prioridad** | Alta |
| **Tipo** | Frontera |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Frontera 500001`.<br>6. En el campo "ID Cliente" escribe: `T3-02`.<br>7. En el campo "Email del cliente" escribe: `t3-02@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Responsabilidad civil`.<br>9. En el campo "Importe reclamado (€)" escribe: `5000.01`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `acta_policial`, `dades_tercer`.<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | amount = 5000.01, claim_type = responsabilitat, docs completos |
| **Resultado esperado** | Píldora = `"Revisión humana requerida"` (`DECISION_STYLE["REVISION_HUMANA"]`); tarjeta "Decisión" = `REVISION_HUMANA`; leyenda bajo el título del expediente con el motivo `importe 5000.01 EUR supera umbral HITL (5000.0 EUR)` (`claim_resolver.py:140`) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T3-03 |
|---|---|
| **ID** | T3-03 |
| **Referencia** | Fórmula `net_payable` de `danys_propis`, `claim_tools.py:107-140` |
| **Título** | Daños propios, importe 5.300,00 € (net_payable exacto 5.000 € tras franquicia) → PAGO |
| **Prioridad** | Media |
| **Tipo** | Frontera |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Franquicia 5300`.<br>6. En el campo "ID Cliente" escribe: `T3-03`.<br>7. En el campo "Email del cliente" escribe: `t3-03@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>9. En el campo "Importe reclamado (€)" escribe: `5300`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `factura`, `denuncia_companyia`.<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | amount = 5300.00, claim_type = danys_propis, docs completos |
| **Resultado esperado** | `net_payable = min(5300,10000) - 300 = 5000.0`; **no** supera el umbral (`> 5000`, no `>=`) → tarjeta "Decisión" = `PAGO`, tarjeta "Importe pagado" = `5,000 €` (nótese: menor que el importe reclamado de 5.300 €, por la franquicia) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T3-04 |
|---|---|
| **ID** | T3-04 |
| **Referencia** | Igual fórmula que T3-03, más `claim_resolver.py:140` |
| **Título** | Daños propios, importe 5.300,01 € → Revisión humana |
| **Prioridad** | Media |
| **Tipo** | Frontera |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Franquicia 530001`.<br>6. En el campo "ID Cliente" escribe: `T3-04`.<br>7. En el campo "Email del cliente" escribe: `t3-04@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>9. En el campo "Importe reclamado (€)" escribe: `5300.01`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `factura`, `denuncia_companyia`.<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | amount = 5300.01, claim_type = danys_propis, docs completos |
| **Resultado esperado** | `net_payable = 5000.01` → tarjeta "Decisión" = `REVISION_HUMANA`, leyenda con el motivo `importe 5000.01 EUR supera umbral HITL (5000.0 EUR)` (`claim_resolver.py:140`) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T3-05 |
|---|---|
| **ID** | T3-05 |
| **Referencia** | Fórmula `net_payable` de `responsabilitat` (franquicia 0), `claim_tools.py:107-140`; comparación `claim_resolver.py:108` |
| **Título** | Responsabilidad civil, importe 4.999,99 € (borde inferior) → PAGO |
| **Prioridad** | Media |
| **Tipo** | Frontera |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Borde Inferior 499999`.<br>6. En el campo "ID Cliente" escribe: `T3-05`.<br>7. En el campo "Email del cliente" escribe: `t3-05@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Responsabilidad civil`.<br>9. En el campo "Importe reclamado (€)" escribe: `4999.99`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `acta_policial`, `dades_tercer`.<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | amount = 4999.99, claim_type = responsabilitat, docs completos |
| **Resultado esperado** | `net_payable = min(4999.99, 50000) - 0 = 4999.99`; no supera el umbral de 5000 → tarjeta "Decisión" = `PAGO`; tarjeta "Importe pagado" = `5,000 €` (el formato `:,.0f` sin decimales redondea 4999.99 al entero más cercano, `streamlit_app.py:365-368`) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## T4 — Falsos positivos OFAC (umbral de similitud 0,82)

**Objetivo:** el cribado antifraude (Agente G) compara el nombre del cliente contra una lista de 15 entidades/personas sancionadas usando similitud de texto (`difflib.SequenceMatcher`, normalizado a minúsculas y sin acentos, `fraud_tools.py:89-96`). El umbral de coincidencia es **`_OFAC_MATCH_THRESHOLD = 0.82`** (`fraud_tools.py:53`). Esto es una fuente real de falsos positivos: nombres parecidos (variantes de transliteración, apellidos comunes, traducciones) pueden superar 0,82 sin ser la misma persona/entidad.

Los valores de similitud de la siguiente tabla **se han calculado ejecutando la función real** `check_ofac_sanctions()` del código (no son estimaciones).

| Campo | T4-01 |
|---|---|
| **ID** | T4-01 |
| **Referencia** | `fraud_tools.py:53,112-145`; lista de sancionados `fraud_tools.py:27-43` |
| **Título** | Variante de transliteración de un nombre sancionado ("Dimitri Volkoff" vs. "Dmitri Volkov") dispara un falso positivo OFAC |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Dimitri Volkoff` (persona **distinta** de la sancionada real "Dmitri Volkov", solo una coincidencia de escritura).<br>6. En el campo "ID Cliente" escribe: `T4-01`.<br>7. En el campo "Email del cliente" escribe: `t4-01@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>9. En el campo "Importe reclamado (€)" escribe: `2500`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `factura`, `denuncia_companyia`.<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | client_name = "Dimitri Volkoff" → similitud real contra "Dmitri Volkov" = **0,8571** (por encima de 0,82) |
| **Resultado esperado** | El caso se bloquea igualmente: píldora `"Bloqueado · Fraude / OFAC"` (`DECISION_STYLE["RECHAZO_FRAUDE"]`), tarjeta "Decisión" = `RECHAZO_FRAUDE`, sección "Cribado antifraude (Agente G)" muestra veredicto `BLOCKED` (`streamlit_app.py:371-378`). Esto **es correcto según el diseño actual** (cualquier similitud ≥ 0,82 basta), pero es un falso positivo real que Miriam debe documentar como límite conocido del cribado, no como bug. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T4-02 |
|---|---|
| **ID** | T4-02 |
| **Referencia** | `fraud_tools.py:53,112-145`; lista de sancionados `fraud_tools.py:27-43` |
| **Título** | Traducción al catalán de una razón social sancionada ("Grup Financer Centaure" vs. "Grupo Financiero Centauro") dispara falso positivo |
| **Prioridad** | Media |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Grup Financer Centaure`.<br>6. En el campo "ID Cliente" escribe: `T4-02`.<br>7. En el campo "Email del cliente" escribe: `t4-02@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>9. En el campo "Importe reclamado (€)" escribe: `2500`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `factura`, `denuncia_companyia`.<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | client_name = "Grup Financer Centaure" → similitud real contra "Grupo Financiero Centauro" = **0,8936** |
| **Resultado esperado** | Píldora `"Bloqueado · Fraude / OFAC"`, tarjeta "Decisión" = `RECHAZO_FRAUDE`, veredicto `BLOCKED` — mismo razonamiento que T4-01 |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T4-03 |
|---|---|
| **ID** | T4-03 |
| **Referencia** | `fraud_tools.py:53,112-145`; lista de sancionados `fraud_tools.py:27-43` |
| **Título** | Nombre parecido pero por debajo del umbral ("Ramirez Fuentes" vs. "Ramirez Fuentes Cartel") NO se bloquea |
| **Prioridad** | Media |
| **Tipo** | Frontera |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Ramirez Fuentes`.<br>6. En el campo "ID Cliente" escribe: `T4-03`.<br>7. En el campo "Email del cliente" escribe: `t4-03@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>9. En el campo "Importe reclamado (€)" escribe: `2500`.<br>10. En el campo "Documentos aportados (tipo)" selecciona estos tres: `foto_danys`, `factura`, `denuncia_companyia`.<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Compara el resultado con lo indicado en "Resultado esperado".<br>15. Haz una captura de pantalla del resultado como evidencia. |
| **Datos de prueba** | client_name = "Ramirez Fuentes" → similitud real contra "Ramirez Fuentes Cartel" = **0,8108** (por debajo de 0,82) |
| **Resultado esperado** | El caso **no** se bloquea por fraude — sigue el flujo normal según importe/documentos (con estos datos, tarjeta "Decisión" = `PAGO`). Confirma que el umbral 0,82 tiene un lado "no dispara" real y verificable, útil como control de que T4-01/T4-02 no bloquean *cualquier* nombre. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

**Tabla de referencia de similitudes calculadas** (para que Miriam pueda construir más casos si quiere ampliar la cobertura):

| Nombre introducido | Entidad más parecida | Similitud | ¿Dispara bloqueo (≥0,82)? |
|---|---|---|---|
| Dimitri Volkoff | Dmitri Volkov | 0,8571 | Sí |
| Grup Financer Centaure | Grupo Financiero Centauro | 0,8936 | Sí |
| Ramirez Fuentes | Ramirez Fuentes Cartel | 0,8108 | No |
| Zoë Müller-Ñíguez | Viktor Nikolaev Kozlov | 0,3077 | No (ver T7-05) |
| `'; DROP TABLE claims;--` | Viktor Nikolaev Kozlov | 0,3396 | No (ver T7-04) |

---

## T5.1 — Conflicto de orden de compuertas: OFAC + documentación incompleta

**Objetivo:** documentar un comportamiento ya conocido y aceptado por el equipo, no "arreglarlo". El orden real de las compuertas es **A → B → C → G → D → E** (`orchestrator.py`, `supervisor_router`, líneas 198-261): el Agente B (validación documental) se ejecuta **antes** que el Agente G (antifraude/OFAC). Si el Agente B marca la documentación como inválida, el flujo corta inmediatamente (`_normalize_final_state`, caso 2, `orchestrator.py:332-341`) **sin llegar nunca a ejecutar el Agente G** — es decir, un cliente sancionado con documentación incompleta recibe `INFO_REQUERIDA`, no `RECHAZO_FRAUDE`.

| Campo | T5.1-01 |
|---|---|
| **ID** | T5.1-01 |
| **Referencia** | `orchestrator.py::_normalize_final_state` líneas 332-341 (caso INFO_REQUERIDA se evalúa aunque el fraude no se haya llegado a comprobar); orden de nodos confirmado en `supervisor_router` líneas 198-261 |
| **Título** | Cliente sancionado (OFAC) con documentación incompleta → INFO_REQUERIDA, no RECHAZO_FRAUDE |
| **Prioridad** | Alta |
| **Tipo** | Funcional (comportamiento de diseño, no bug) |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Viktor Nikolaev Kozlov` (coincidencia exacta con la lista OFAC, similitud 1,0000).<br>6. En el campo "ID Cliente" escribe: `T5.1-01`.<br>7. En el campo "Email del cliente" escribe: `t51-01@example.com`.<br>8. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>9. En el campo "Importe reclamado (€)" escribe: `2500`.<br>10. En el campo "Documentos aportados (tipo)" selecciona solo: `factura` (deja sin marcar `foto_danys` y `denuncia_companyia`, que también son obligatorios para este tipo).<br>11. No es necesario subir ningún archivo.<br>12. Haz clic en el botón "Procesar reclamación".<br>13. Espera a que aparezca el resultado debajo del formulario.<br>14. Fíjate en el "stepper" horizontal de agentes (círculos A→B→C→G→D→E) que aparece justo encima de las tarjetas de métricas.<br>15. Compara el resultado con lo indicado en "Resultado esperado".<br>16. Haz una captura de pantalla del resultado completo, incluyendo el stepper. |
| **Datos de prueba** | client_name = "Viktor Nikolaev Kozlov" (sancionado real), documents = ["factura"] |
| **Resultado esperado** | Píldora = `"Información requerida"` (`DECISION_STYLE["INFO_REQUERIDA"]`), tarjeta "Decisión" = `INFO_REQUERIDA`, **no** `RECHAZO_FRAUDE`. En el stepper de agentes, el círculo "G" debe verse en gris (no visitado, `streamlit_app.py:322-349`), confirmando que el flujo se detuvo en B sin llegar a ejecutar el Agente G. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla, incluyendo el stepper de agentes visible bajo el resultado |
| **Nota para el informe** | Este es el "T5.1 finding" ya anticipado por el equipo: aceptable porque no se realiza ningún pago en ningún caso, pero debe documentarse como decisión de diseño deliberada, no dejarse parecer un accidente. |

---

## T6 — Degradación de servicios (5 escenarios)

**Objetivo:** demostrar que el sistema nunca se rompe ni bloquea el flujo cuando un servicio externo falla — siempre cae a un camino determinista con una decisión legible. Estos 5 casos requieren arrancar la app **en tu propio ordenador** (no en la nube) con una variable de entorno modificada a propósito, porque necesitas controlar exactamente qué servicio está o no disponible — algo que no puedes hacer sobre la app ya desplegada en Streamlit Cloud.

**Aviso general para todos los casos de esta sección — orden de carga de variables:** `streamlit_app.py` fija `SCA_RAG_ENABLED=1` por defecto **antes** de leer el fichero `.env` (`os.environ.setdefault("SCA_RAG_ENABLED", "1")` en la línea 38, seguido de `load_dotenv(find_dotenv())` en las líneas 40-44). La librería `python-dotenv` **nunca sobreescribe una variable que ya esté presente** en el entorno del proceso. Esto significa que **editar el fichero `.env` no sirve para cambiar `SCA_RAG_ENABLED`** cuando se arranca con `streamlit run` — hay que definir la variable directamente en la terminal (con `$env:...`) *antes* de lanzar `streamlit run`, para que ya esté presente cuando el script llega a la línea 38. Para `ANTHROPIC_API_KEY` sí funciona editar `.env` (no tiene ese `setdefault` previo), pero en estos casos se usa también la terminal por consistencia y porque es más fácil de restaurar (basta con cerrar la terminal).

| Campo | T6-01 |
|---|---|
| **ID** | T6-01 |
| **Referencia** | `reasoning.py:38-39` (`if not os.getenv("ANTHROPIC_API_KEY"): return fallback`) |
| **Título** | Sin clave de Anthropic → razonamiento determinista, decisión sin cambios |
| **Prioridad** | Alta |
| **Tipo** | Degradación |
| **Entorno** | Local — app con entorno modificado |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador y Python 3.11 instalado. |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta raíz del proyecto (donde está `streamlit_app.py`): `cd C:\proyectos\smart-claims-agent-vfull` (sustituye por la ruta real).<br>3. Instala las dependencias si no lo has hecho antes: `py -m pip install -r requirements.txt`.<br>4. Asegura que esta sesión de terminal no tiene la clave definida: `Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue`.<br>5. Si existe un fichero `.env` en la raíz del proyecto, ábrelo con `notepad .env` y comprueba la línea `ANTHROPIC_API_KEY=...`. Si tiene un valor (real o de ejemplo), bórralo dejando solo `ANTHROPIC_API_KEY=` o coméntala con `# ANTHROPIC_API_KEY=...`. Guarda y cierra Notepad. Si no existe `.env`, no hace falta crearlo para este caso.<br>6. Arranca la app: `py -m streamlit run streamlit_app.py`.<br>7. Espera a que se abra el navegador en `http://localhost:8501` (si no se abre solo, ábrelo tú manualmente en esa dirección).<br>8. Comprueba en la barra lateral, debajo del botón "Caso libre", que aparece el texto "⚪ Modo fallback determinista (sin clave)" (`streamlit_app.py:428-430`).<br>9. En la barra lateral, haz clic en "Nueva reclamación".<br>10. En la sección "Escenarios rápidos", localiza la tarjeta "Pago automático" (primera de las cinco) y pulsa su botón "Procesar".<br>11. Espera a que aparezca el resultado.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla de la sección "Cadena de razonamiento de los agentes".<br>14. **Para restaurar el entorno:** si comentaste o borraste la línea `ANTHROPIC_API_KEY=` en `.env`, ábrelo de nuevo con `notepad .env` y restaura el valor real (o quita el `#`). Si no tocaste `.env`, no hay nada que restaurar — cierra la terminal cuando termines (las variables definidas con `$env:` no persisten a la siguiente sesión). |
| **Datos de prueba** | Escenario de demo "Pago automático": claim_type = danys_propis, amount = 2.500,00 €, docs completos (`foto_danys`, `factura`, `denuncia_companyia`) — `DEMO_SCENARIOS[0]`, `streamlit_app.py:108-110` |
| **Resultado esperado** | El caso se resuelve igual (tarjeta "Decisión" = `PAGO`), sin error ni excepción visible; el texto de razonamiento mostrado en cada tarjeta de agente es el `fallback` determinista construido en el propio código de cada agente, no un texto generado por Claude |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de la sección "Cadena de razonamiento de los agentes" |

| Campo | T6-02 |
|---|---|
| **ID** | T6-02 |
| **Referencia** | `reasoning.py:41-56` (timeout=20 en la línea 44, captura de `Exception` genérica en línea 52) |
| **Título** | Clave de Anthropic inválida → fallback tras el intento fallido, sin romper el flujo |
| **Prioridad** | Media |
| **Tipo** | Degradación |
| **Entorno** | Local — app con entorno modificado |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador y Python 3.11 instalado. |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta raíz del proyecto: `cd C:\proyectos\smart-claims-agent-vfull` (sustituye por la ruta real).<br>3. Instala las dependencias si no lo has hecho antes: `py -m pip install -r requirements.txt`.<br>4. Define una clave inválida solo para esta sesión de terminal: `$env:ANTHROPIC_API_KEY = "sk-ant-invalido-000"`. Esta variable, al estar ya presente cuando arranque Python, tiene prioridad sobre cualquier valor que hubiera en `.env` — no hace falta tocar `.env` para este caso.<br>5. Arranca la app: `py -m streamlit run streamlit_app.py`.<br>6. Espera a que se abra el navegador en `http://localhost:8501`.<br>7. Comprueba en la barra lateral que aparece el texto "🟢 Claude activo (CoT enriquecido)" (`streamlit_app.py:428-430`) — aparece este texto porque la variable está definida, aunque el valor sea inválido (el chequeo del sidebar solo comprueba si hay algo en la variable, no si es correcto).<br>8. En la barra lateral, haz clic en "Nueva reclamación".<br>9. En la sección "Escenarios rápidos", localiza la tarjeta "Pago automático" y pulsa su botón "Procesar".<br>10. Fíjate en la tarjeta "Tiempo" del resultado (puede tardar unos segundos más de lo normal, porque primero intenta la llamada real a la API y falla, antes de caer al fallback).<br>11. Compara con "Resultado esperado".<br>12. Haz una captura de pantalla del resultado completo, incluyendo la tarjeta "Tiempo".<br>13. **Para restaurar el entorno:** cierra esta terminal (la variable `$env:ANTHROPIC_API_KEY` definida en el paso 4 no persiste a la siguiente sesión de terminal), o ejecuta `Remove-Item Env:ANTHROPIC_API_KEY` en la misma sesión si vas a seguir usándola para otro caso. |
| **Datos de prueba** | Igual escenario que T6-01, con clave inválida `sk-ant-invalido-000` en vez de ausente |
| **Resultado esperado** | El caso se resuelve igual (tarjeta "Decisión" = `PAGO`); puede tardar unos segundos más (el intento real a la API falla antes de caer al fallback) pero nunca supera ~20 segundos por llamada (timeout configurado en `reasoning.py:44`) ni se muestra ningún error al usuario |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla + tiempo mostrado en la tarjeta "Tiempo" |

| Campo | T6-03 |
|---|---|
| **ID** | T6-03 |
| **Referencia** | `coverage_checker.py:30` (`if not os.getenv("SCA_RAG_ENABLED"): return None`); orden de carga `streamlit_app.py:36-44` |
| **Título** | RAG de pólizas desactivado → Agente D usa el catálogo determinista sin romper el flujo |
| **Prioridad** | Media |
| **Tipo** | Degradación |
| **Entorno** | Local — app con entorno modificado |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador y Python 3.11 instalado. |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta raíz del proyecto: `cd C:\proyectos\smart-claims-agent-vfull` (sustituye por la ruta real).<br>3. Instala las dependencias si no lo has hecho antes: `py -m pip install -r requirements.txt`.<br>4. Define la variable con un valor **vacío** (no `"0"`) solo para esta sesión de terminal: `$env:SCA_RAG_ENABLED = ""`. Importante: el fichero `.env.example` sugiere en su comentario que `0` también desactiva el RAG (`.env.example:29`, "vacío/0 = usa el catálogo determinista"), pero el código real solo comprueba si la variable es "falsy" con `if not os.getenv(...)` (`coverage_checker.py:30`) — y en Python la cadena de texto `"0"` **es verdadera** (no vacía), así que `SCA_RAG_ENABLED=0` **no** desactivaría el RAG. Solo una cadena vacía (o la variable ausente) lo desactiva de verdad. Usa exactamente `""` como en este paso, no `"0"`.<br>5. Arranca la app: `py -m streamlit run streamlit_app.py`. Al arrancar, la línea `os.environ.setdefault("SCA_RAG_ENABLED", "1")` (`streamlit_app.py:38`) no tocará esta variable porque ya está presente (aunque vacía) desde el paso 4.<br>6. Espera a que se abra el navegador en `http://localhost:8501`.<br>7. En la barra lateral, haz clic en "Nueva reclamación".<br>8. En la sección "Escenarios rápidos", localiza la tarjeta "Pago automático" y pulsa su botón "Procesar".<br>9. Espera a que aparezca el resultado.<br>10. Comprueba que **no** aparece ninguna sección titulada "Cobertura (Agente D · RAG sobre pólizas)" entre las tarjetas de métricas y la sección de razonamiento.<br>11. Compara con "Resultado esperado".<br>12. Haz una captura de pantalla del resultado completo, mostrando que ese bloque no está presente.<br>13. **Para restaurar el entorno:** cierra esta terminal, o ejecuta `Remove-Item Env:SCA_RAG_ENABLED` en la misma sesión. |
| **Datos de prueba** | Igual escenario que T6-01 |
| **Resultado esperado** | El caso se resuelve igual (tarjeta "Decisión" = `PAGO`); en el resultado **no** aparece la sección "Cobertura (Agente D · RAG sobre pólizas)" (solo se muestra si `coverage_result.source == "rag"`, `streamlit_app.py:380-387`) |
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
| **Entorno** | Local — app con entorno modificado |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador, Python 3.11 instalado, y una imagen cualquiera (PNG o JPG, cualquier contenido, por ejemplo una captura de pantalla) guardada en tu ordenador. |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta raíz del proyecto: `cd C:\proyectos\smart-claims-agent-vfull` (sustituye por la ruta real).<br>3. Instala las dependencias si no lo has hecho antes: `py -m pip install -r requirements.txt`.<br>4. Asegura que esta sesión de terminal no tiene la clave definida: `Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue`.<br>5. Si existe un fichero `.env` en la raíz del proyecto, ábrelo con `notepad .env` y borra o comenta la línea `ANTHROPIC_API_KEY=...`. Guarda y cierra. Si no existe `.env`, no hace falta crearlo.<br>6. Arranca la app: `py -m streamlit run streamlit_app.py`.<br>7. Espera a que se abra el navegador en `http://localhost:8501`.<br>8. En la barra lateral, haz clic en "Nueva reclamación".<br>9. Baja hasta la sección "O crea una reclamación personalizada".<br>10. Rellena "Nombre del asegurado" = `Test Vision Sin Clave`, "ID Cliente" = `T6-04`, "Tipo de siniestro" = `Daños propios`, "Importe reclamado (€)" = `1200`.<br>11. En "Documentos aportados (tipo)" selecciona: `foto_danys`, `factura`, `denuncia_companyia`.<br>12. En el campo "Sube los documentos reales (factura, foto de daños, acta...) — el Agente C los analizará con Claude Vision", haz clic y selecciona tu imagen de prueba.<br>13. Haz clic en el botón "Procesar reclamación".<br>14. Espera a que aparezca el resultado.<br>15. Compara con "Resultado esperado".<br>16. Haz una captura de pantalla del resultado.<br>17. **Para restaurar el entorno:** si comentaste/borraste la línea en `.env`, restáurala abriendo `notepad .env` de nuevo. |
| **Datos de prueba** | claim_type = danys_propis, amount = 1.200,00 €, docs completos, un archivo de imagen cualquiera subido |
| **Resultado esperado** | El flujo termina con una decisión normal (`PAGO`), sin traceback en pantalla; la sección "Extracción multimodal real (Agente C · Claude Vision)" **no** aparece, porque solo se muestra cuando `extraction.source == "claude_vision"` (`streamlit_app.py:389-407`) — sin clave, `analyze_document()` devuelve `None` y el Agente C usa su camino simulado en su lugar |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T6-05 |
|---|---|
| **ID** | T6-05 |
| **Referencia** | `orchestrator.py:419-441` (persistencia best-effort envuelta en `try/except`, `logger.warning` en líneas 440-441) |
| **Título** | Base de datos MariaDB no disponible → el resultado se muestra igualmente, sin excepción visible |
| **Prioridad** | Media |
| **Tipo** | Degradación |
| **Entorno** | Local — app con entorno modificado |
| **Precondiciones** | Tienes el repositorio del proyecto en tu ordenador y Python 3.11 instalado. No tienes Docker Desktop arrancado (o, si lo tienes, no has ejecutado `docker compose up` en este proyecto) — así no hay ninguna instancia de MariaDB accesible en `localhost`/`mariadb`. |
| **Pasos** | 1. Abre una terminal PowerShell.<br>2. Navega a la carpeta raíz del proyecto: `cd C:\proyectos\smart-claims-agent-vfull` (sustituye por la ruta real).<br>3. Instala las dependencias si no lo has hecho antes: `py -m pip install -r requirements.txt`.<br>4. Arranca la app **sin** usar Docker Compose, directamente con Streamlit: `py -m streamlit run streamlit_app.py`. Al ejecutarse así (modo standalone, `README.md:49-56`), la app nunca llega a tener un MariaDB real accesible en el host `mariadb` (nombre de servicio Docker que solo existe dentro de la red de contenedores) — es la forma más simple y fiable de reproducir este caso.<br>5. Espera a que se abra el navegador en `http://localhost:8501`.<br>6. En la barra lateral, haz clic en "Nueva reclamación".<br>7. En la sección "Escenarios rápidos", localiza la tarjeta "Pago automático" y pulsa su botón "Procesar".<br>8. Espera a que aparezca el resultado.<br>9. Comprueba que el resultado se muestra con normalidad, sin ningún mensaje de error rojo en pantalla.<br>10. Vuelve a la ventana de la terminal (sin cerrarla) y busca si aparece alguna línea de aviso (`WARNING`) relacionada con la conexión a la base de datos — el texto exacto de ese aviso no se ha podido verificar literalmente para este documento, márcalo `[VERIFICAR]` si quieres citarlo textualmente en el informe.<br>11. Compara con "Resultado esperado".<br>12. Haz una captura de pantalla del resultado en el navegador, y opcionalmente otra de la terminal si se ve el aviso.<br>13. **Para restaurar el entorno:** no se ha modificado nada persistente (no se editó `.env` ni se definió ninguna variable); basta con cerrar la terminal. Si quieres volver a tener MariaDB disponible para otras pruebas, arranca el stack completo con Docker Compose como se describe en `README.md`, sección 6. |
| **Datos de prueba** | Igual escenario que T6-01 |
| **Resultado esperado** | El resultado se muestra con normalidad (tarjeta "Decisión" = `PAGO`); no aparece ningún error en pantalla (blindaje A3, `streamlit_app.py:276-279`); el fallo de persistencia solo queda registrado en el log del servidor (`logger.warning`, `orchestrator.py:440-441`), nunca visible al usuario |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla del navegador + (si es visible) captura de la terminal con el aviso |

---

## T7 — Entradas adversarias vía interfaz

**Objetivo:** probar el blindaje A1 (`validate_claim_input`, `orchestrator.py:50-106`) a través de lo que realmente es alcanzable desde la interfaz. **Aviso importante:** el formulario de "Nueva reclamación" restringe varias entradas en el propio widget (p. ej. `number_input(min_value=0.0, max_value=100000.0)` para el importe, `streamlit_app.py:578`, y el `selectbox` de tipo de siniestro solo ofrece los 4 tipos válidos, `streamlit_app.py:575-577`). Por eso, algunas ramas de `validate_claim_input` (importe negativo, importe NaN/infinito, importe ≥ 10.000.000, tipo de siniestro desconocido) **no son alcanzables desde ese formulario concreto** — pero sí lo son desde el panel "Caso libre" (ver esa sección más abajo), que usa campos de texto libre sin ningún límite. Los casos siguientes prueban lo que sí es alcanzable directamente desde "Nueva reclamación".

| Campo | T7-01 |
|---|---|
| **ID** | T7-01 |
| **Referencia** | `validate_claim_input`, rama 1, `orchestrator.py:62-76`; cadena exacta `f"importe reclamado invalido: {amount_requested!r}"` |
| **Título** | Importe reclamado = 0 € → Rechazo automático |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Importe Cero`.<br>6. En el campo "ID Cliente" escribe: `T7-01`.<br>7. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>8. En el campo "Importe reclamado (€)" escribe: `0`.<br>9. En el campo "Documentos aportados (tipo)" selecciona: `foto_danys`, `factura`, `denuncia_companyia`.<br>10. Haz clic en el botón "Procesar reclamación".<br>11. Espera a que aparezca el resultado.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | amount = 0.0 |
| **Resultado esperado** | Píldora = `"Rechazado · Sin cobertura"` (`DECISION_STYLE["RECHAZO"]`); tarjeta "Decisión" = `RECHAZO`; leyenda del motivo = `importe reclamado invalido: 0.0` |
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
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" copia y pega este texto de 201 caracteres (o cualquier texto propio que compruebes que supera 200 caracteres con un contador de caracteres online): `Juan García Fernández López Martínez de la Torre y Sánchez del Río Rodríguez Pérez González Álvarez Domínguez Ruiz Jiménez Moreno Muñoz Álvarez Romero Alonso Gutiérrez Navarro Torres Domingueza`.<br>6. En el campo "ID Cliente" escribe: `T7-02`.<br>7. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>8. En el campo "Importe reclamado (€)" escribe: `2500`.<br>9. En el campo "Documentos aportados (tipo)" selecciona: `foto_danys`, `factura`, `denuncia_companyia`.<br>10. Haz clic en el botón "Procesar reclamación".<br>11. Espera a que aparezca el resultado.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | Nombre de 201 caracteres, ver paso 5 |
| **Resultado esperado** | Píldora = `"Revisión humana requerida"`; tarjeta "Decisión" = `REVISION_HUMANA`; leyenda del motivo = `nombre del asegurado invalido (vacio o excesivamente largo)` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T7-03 |
|---|---|
| **ID** | T7-03 |
| **Referencia** | `document_validator.py` (Agente B), catálogo `REQUIRED_DOCS_BY_TYPE` (`streamlit_app.py:91-96`) |
| **Título** | Ningún documento aportado → Información requerida (todos los documentos figuran como faltantes) |
| **Prioridad** | Baja |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Sin Documentos`.<br>6. En el campo "ID Cliente" escribe: `T7-03`.<br>7. En el desplegable "Tipo de siniestro" selecciona: `Robo`.<br>8. En el campo "Importe reclamado (€)" escribe: `1000`.<br>9. Deja el campo "Documentos aportados (tipo)" sin seleccionar nada.<br>10. Haz clic en el botón "Procesar reclamación".<br>11. Espera a que aparezca el resultado.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | claim_type = robatori, documents = [] |
| **Resultado esperado** | Píldora = `"Información requerida"`; tarjeta "Decisión" = `INFO_REQUERIDA`; leyenda menciona los dos documentos requeridos para robo: `acta_policial, llista_objectes_robats` (`REQUIRED_DOCS_BY_TYPE["robatori"]`, `streamlit_app.py:94`) |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | T7-04 |
|---|---|
| **ID** | T7-04 |
| **Referencia** | `backend/app/db/repository.py:34-93` (`save_claim`, `log_agent_decision` — ambos construyen objetos SQLAlchemy `Claim`/`AgentDecision` con `s.add(...)` y `await s.commit()`, nunca SQL crudo ni f-strings con datos del usuario); `validate_claim_input`, rama 3, `orchestrator.py:88-97` (el nombre solo se rechaza si está vacío o supera 200 caracteres, no por su contenido) |
| **Título** | Inyección SQL en el nombre del asegurado → flujo normal, sin error, sin bloqueo; "Historial" sigue cargando después |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe exactamente: `'; DROP TABLE claims;--`.<br>6. En el campo "ID Cliente" escribe: `T7-04`.<br>7. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>8. En el campo "Importe reclamado (€)" escribe: `2500`.<br>9. En el campo "Documentos aportados (tipo)" selecciona: `foto_danys`, `factura`, `denuncia_companyia`.<br>10. Haz clic en el botón "Procesar reclamación".<br>11. Espera a que aparezca el resultado. Comprueba que **no** aparece ningún mensaje de error técnico ni traceback en pantalla.<br>12. Compara el resultado con lo indicado en "Resultado esperado" (primera parte).<br>13. Haz una captura de pantalla del resultado.<br>14. Ahora, en la barra lateral izquierda, haz clic en el botón "Historial".<br>15. Comprueba que la vista carga con normalidad, mostrando el título "## Historial de reclamaciones" y (si has procesado casos en esta misma sesión del navegador) una tabla con las reclamaciones procesadas, sin ningún error en pantalla.<br>16. Haz una captura de pantalla de la vista "Historial" cargada correctamente. |
| **Datos de prueba** | client_name = `'; DROP TABLE claims;--`, claim_type = danys_propis, amount = 2.500,00 €, docs completos. Similitud OFAC de este texto contra la entidad sancionada más parecida = 0,3396 (muy por debajo de 0,82; no dispara bloqueo antifraude, ver tabla de T4) |
| **Resultado esperado** | El caso se procesa con normalidad: tarjeta "Decisión" = `PAGO` (mismos datos que el escenario "Pago automático", solo cambia el nombre), sin ningún error ni traceback visible. La cadena se guarda tal cual como texto normal en la base de datos, porque tanto `save_claim` como `log_agent_decision` (`repository.py:34-93`) construyen los registros mediante el ORM de SQLAlchemy (`s.add(Claim(...))`, `s.add(AgentDecision(...))`), que usa parámetros enlazados internamente — nunca concatena el texto del usuario dentro de una sentencia SQL, así que el fragmento `DROP TABLE` no se ejecuta como comando. Después, la vista "Historial" (`streamlit_app.py:697-714`) sigue cargando con normalidad, confirmando que no se ha dañado ninguna tabla. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla del resultado + captura de la vista "Historial" cargando con normalidad |

| Campo | T7-05 |
|---|---|
| **ID** | T7-05 |
| **Referencia** | `fraud_tools.py:53,89-96,112-145` (normalización y umbral OFAC) |
| **Título** | Nombre unicode benigno (acentos, diéresis, ñ) → flujo normal, sin falso positivo OFAC |
| **Prioridad** | Media |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe exactamente: `Zoë Müller-Ñíguez`.<br>6. En el campo "ID Cliente" escribe: `T7-05`.<br>7. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>8. En el campo "Importe reclamado (€)" escribe: `2500`.<br>9. En el campo "Documentos aportados (tipo)" selecciona: `foto_danys`, `factura`, `denuncia_companyia`.<br>10. Haz clic en el botón "Procesar reclamación".<br>11. Espera a que aparezca el resultado.<br>12. Comprueba la sección "Cribado antifraude (Agente G)".<br>13. Compara con "Resultado esperado".<br>14. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | client_name = "Zoë Müller-Ñíguez" → mejor similitud real contra la lista de sancionados = **0,3077** (muy por debajo de 0,82) |
| **Resultado esperado** | El caso se procesa con normalidad: tarjeta "Decisión" = `PAGO`; sección "Cribado antifraude (Agente G)" muestra veredicto `CLEAR` (no `FLAGGED`), sin bloqueo pese a llevar caracteres unicode (acentos, diéresis, eñe) — la normalización de `check_ofac_sanctions()` (NFD, minúsculas, sin acentos, `fraud_tools.py:89-92`) no provoca aquí ninguna coincidencia falsa |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## CASO LIBRE — Panel de reserva para peticiones improvisadas (blindaje A5)

**Objetivo:** el panel "Caso libre" (`streamlit_app.py:603-643`) es un backup pensado para que, si el tribunal pide en directo probar algo fuera de los escenarios ya preparados, el equipo tenga un sitio donde introducir cualquier valor — incluido uno pensado para romper el sistema — sin depender de tener acceso al código en ese momento. A diferencia de "Nueva reclamación" (que usa un desplegable con los 4 tipos válidos y un campo numérico con tope de 100.000 €), aquí los cinco campos son de texto libre (`st.text_input`) sin ningún límite ni validación previa del propio widget: se puede escribir un tipo de siniestro inventado, un importe no numérico, o un nombre de cualquier longitud. Todo eso llega tal cual al mismo blindaje de entrada (Agente A, `validate_claim_input`) que protege el resto de la aplicación.

**Dato importante sobre el orden de validación:** dentro de `validate_claim_input()` (`orchestrator.py:50-106`), el importe se valida **antes** que el tipo de siniestro (rama 1, líneas 62-76, se ejecuta antes que la rama 2, líneas 78-86). Esto significa que si en "Caso libre" se rompen a la vez el importe **y** el tipo de siniestro, el sistema siempre responde con el motivo del importe (`RECHAZO`), nunca llega a evaluar si el tipo de siniestro es reconocido. Los casos siguientes están diseñados para dejarlo claro.

| Campo | LIBRE-01 |
|---|---|
| **ID** | LIBRE-01 |
| **Referencia** | `process_libre`, `streamlit_app.py:287-310`; vista "libre", `streamlit_app.py:603-643` |
| **Título** | Caso libre con datos válidos (caso feliz) → se procesa igual que un caso normal |
| **Prioridad** | Media |
| **Tipo** | Funcional |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Caso libre" (el último de la lista de navegación).<br>4. Espera a que cargue la vista "## Caso libre", con su texto explicativo sobre el panel de reserva.<br>5. En el campo "Nombre del asegurado" escribe: `Caso Libre Feliz`.<br>6. En el campo "ID Cliente" escribe: `LIBRE-01`.<br>7. En el campo "Tipo de siniestro" (aquí es un campo de texto libre, no un desplegable) escribe exactamente: `danys_propis`.<br>8. En el campo "Importe reclamado" (también texto libre) escribe: `2500`.<br>9. En el campo "Documentos aportados (separados por comas)" escribe: `foto_danys, factura, denuncia_companyia`.<br>10. Haz clic en el botón "Procesar caso libre".<br>11. Espera a que aparezca el resultado debajo del panel.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | client_name = "Caso Libre Feliz", claim_type (texto) = "danys_propis", amount (texto) = "2500", documents (texto separado por comas) = "foto_danys, factura, denuncia_companyia" |
| **Resultado esperado** | Aunque los campos sean de texto libre, al escribir valores que coinciden exactamente con el catálogo real (`danys_propis` está en `CLAIM_TYPE_CATALOG`, `"2500"` se convierte a `float` sin error en `streamlit_app.py:631-632`), el caso se comporta exactamente igual que si se hubiera enviado desde "Nueva reclamación": tarjeta "Decisión" = `PAGO`, tarjeta "Importe pagado" = `2,500 €` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | LIBRE-02 |
|---|---|
| **ID** | LIBRE-02 |
| **Referencia** | `validate_claim_input`, rama 1, `orchestrator.py:62-76`; conversión de importe en `streamlit_app.py:630-636` (`try: amount_value = float(amount_text) except ValueError: amount_value = amount_text`, se deja el texto tal cual para que lo capture el blindaje A1); test automático que confirma este comportamiento exacto: `backend/tests/test_streamlit_ui.py:91-116` (`test_caso_libre_view_lets_broken_amount_trigger_blindaje_a1`) |
| **Título** | Caso libre con tipo de siniestro y ambos importe roto (caso roto) → RECHAZO por el importe, sin llegar a evaluar el tipo |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Caso libre".<br>4. Espera a que cargue la vista "## Caso libre".<br>5. En el campo "Nombre del asegurado" escribe: `Caso Libre Roto`.<br>6. En el campo "ID Cliente" escribe: `LIBRE-02`.<br>7. En el campo "Tipo de siniestro" escribe un tipo inventado que no existe en el catálogo: `tipo-inventado-por-el-tribunal`.<br>8. En el campo "Importe reclamado" escribe un valor que no es un número: `no-es-un-numero`.<br>9. Deja el campo "Documentos aportados (separados por comas)" vacío.<br>10. Haz clic en el botón "Procesar caso libre".<br>11. Espera a que aparezca el resultado debajo del panel. Comprueba que **no** aparece ningún traceback ni mensaje técnico, solo una decisión legible.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | client_name = "Caso Libre Roto", claim_type (texto) = "tipo-inventado-por-el-tribunal", amount (texto) = "no-es-un-numero" |
| **Resultado esperado** | Píldora = `"Rechazado · Sin cobertura"`; tarjeta "Decisión" = `RECHAZO`; leyenda del motivo = `importe reclamado invalido: 'no-es-un-numero'` (exactamente la cadena que verifica el test automático citado en "Referencia"). El sistema **nunca llega a evaluar** si `tipo-inventado-por-el-tribunal` es un tipo de siniestro válido, porque `validate_claim_input` corta en la rama del importe (rama 1) antes de llegar a la rama del tipo de siniestro (rama 2) — confirma en la práctica el "dato importante sobre el orden de validación" explicado al principio de esta sección. |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | LIBRE-03 |
|---|---|
| **ID** | LIBRE-03 |
| **Referencia** | `streamlit_app.py:625-627` (`if not libre_claim_type and not libre_amount: st.warning(...)`) |
| **Título** | Caso libre sin tipo de siniestro ni importe → aviso de campos obligatorios, no se procesa nada |
| **Prioridad** | Baja |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Caso libre".<br>4. Espera a que cargue la vista "## Caso libre".<br>5. Deja todos los campos vacíos (Nombre del asegurado, ID Cliente, Tipo de siniestro, Importe reclamado, Documentos aportados).<br>6. Haz clic directamente en el botón "Procesar caso libre" sin rellenar nada.<br>7. Observa el mensaje que aparece.<br>8. Compara con "Resultado esperado".<br>9. Haz una captura de pantalla del aviso. |
| **Datos de prueba** | Todos los campos vacíos |
| **Resultado esperado** | Aviso amarillo con el texto exacto `"Indica al menos el tipo de siniestro y el importe reclamado."` (`streamlit_app.py:627`, misma cadena que usa el formulario de "Nueva reclamación" en `streamlit_app.py:590`); no se llega a invocar `process_libre`, no aparece ningún resultado ni traceback |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## DEMO — Los 5 escenarios de demostración, ejecutados 10 veces cada uno

`DEMO_SCENARIOS` (`streamlit_app.py:107-124`) define 5 escenarios, uno por cada camino posible del flujo de agentes. Los 5 escenarios reales, verbatim:

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
| **Referencia** | `streamlit_app.py:107-124,552-564` |
| **Título** | Cada uno de los 5 escenarios rápidos se ejecuta 10 veces seguidas sin fallos ni variación de decisión |
| **Prioridad** | Alta |
| **Tipo** | Regresión |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. En la sección "Escenarios rápidos" verás 5 tarjetas, cada una con un botón "Procesar" debajo.<br>5. Pulsa el botón "Procesar" de la primera tarjeta ("Pago automático"). Espera el resultado y anota la "Decisión" que muestra.<br>6. Vuelve a pulsar el mismo botón "Procesar" de esa misma tarjeta otras 9 veces más (10 repeticiones en total para este escenario), anotando la decisión de cada intento.<br>7. Repite el paso 5 y 6 para la segunda tarjeta ("Revisión humana (HITL)"): 10 repeticiones, anotando cada decisión.<br>8. Repite para la tercera tarjeta ("Información requerida"): 10 repeticiones.<br>9. Repite para la cuarta tarjeta ("Rechazo por no cobertura"): 10 repeticiones.<br>10. Repite para la quinta tarjeta ("Bloqueo por fraude (OFAC)"): 10 repeticiones.<br>11. Con las 50 anotaciones (5 escenarios × 10 repeticiones), compara cada una contra la columna "Resultado esperado" de la tabla de esta sección.<br>12. Anota si en algún momento apareció una excepción o traceback visible en pantalla. |
| **Datos de prueba** | Los 5 escenarios de la tabla anterior |
| **Resultado esperado** | Las 10 repeticiones de cada escenario devuelven exactamente la misma `decision` que la tabla; 0 excepciones visibles en pantalla en las 50 ejecuciones totales |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Tabla de 50 filas (5 escenarios × 10 repeticiones) con la decisión obtenida en cada una |

---

## BANDEJA — Vista "Bandeja" (casos entrantes por WhatsApp simulado)

**Objetivo:** verificar los 2 casos fijos de la vista Bandeja (`streamlit_fixtures.py::BANDEJA_CASES`), que reutilizan el mismo camino ya blindado (`process_and_store`), confirmado por el test automático `test_streamlit_ui.py::test_bandeja_view_shows_fixture_cases_and_processes_pago_automatico`.

| Campo | BANDEJA-01 |
|---|---|
| **ID** | BANDEJA-01 |
| **Referencia** | `streamlit_fixtures.py` líneas 34-61 (caso `CLM-WA-0001`); botón `bandeja_process_CLM-WA-0001`, `streamlit_app.py:529-535` |
| **Título** | Caso CLM-WA-0001 (Marta Soler Puig, documentación completa) → PAGO al procesar |
| **Prioridad** | Alta |
| **Tipo** | Funcional |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Bandeja".<br>4. Espera a que cargue la vista "## Bandeja de entrada".<br>5. Localiza la tarjeta cuyo identificador es `CLM-WA-0001` y cuyo nombre de cliente es "Marta Soler Puig".<br>6. Dentro de esa tarjeta, comprueba que aparece un mensaje de chat mencionando el número de denuncia `D-4521`.<br>7. Comprueba que bajo "Adjuntos recibidos" aparecen dos fotos y una factura (con miniatura de PDF), y que el aviso verde dice "Documentación completa para este tipo de siniestro."<br>8. Pulsa el botón "Revisar y procesar" de esa misma tarjeta.<br>9. Espera a que aparezca el resultado dentro de la propia tarjeta, debajo de un separador.<br>10. Compara con "Resultado esperado".<br>11. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | Ninguno (caso fijo): claim_type = danys_propis, amount = 3.200,00 €, documents = [foto_danys, factura, denuncia_companyia] (completos) |
| **Resultado esperado** | Tras procesar, aparece la píldora "Resuelto · Pago aprobado" en el resultado; tarjeta "Decisión" = `PAGO` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | BANDEJA-02 |
|---|---|
| **ID** | BANDEJA-02 |
| **Referencia** | `streamlit_fixtures.py` líneas 62-83 (caso `CLM-WA-0002`, comentario explícito: "Documentación incompleta a propósito"); botón `bandeja_process_CLM-WA-0002`, `streamlit_app.py:529-535` |
| **Título** | Caso CLM-WA-0002 (Jordi Ferrer Camps, solo 1 documento de 3) → Información requerida al procesar |
| **Prioridad** | Media |
| **Tipo** | Funcional |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Bandeja".<br>4. Espera a que cargue la vista "## Bandeja de entrada".<br>5. Localiza la tarjeta cuyo identificador es `CLM-WA-0002` y cuyo nombre de cliente es "Jordi Ferrer Camps".<br>6. Comprueba que bajo "Adjuntos recibidos" solo aparece una foto, y que el aviso amarillo dice algo del tipo "Documentación incompleta: falta(n) factura, denuncia_companyia."<br>7. Pulsa el botón "Revisar y procesar" de esa misma tarjeta.<br>8. Espera a que aparezca el resultado dentro de la propia tarjeta.<br>9. Compara con "Resultado esperado".<br>10. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | Caso fijo: claim_type = danys_propis, amount = 2.900,00 €, documents = [foto_danys] únicamente (faltan factura y denuncia_companyia) |
| **Resultado esperado** | Tarjeta "Decisión" = `INFO_REQUERIDA`; el motivo menciona los documentos que faltan: `factura, denuncia_companyia` |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## BLINDAJE — Entradas rotas desde la interfaz (A1/A2/A3)

**Objetivo:** confirmar en pantalla, no solo en tests automáticos, que el blindaje A1 (validación de entrada), A2 (captura global de errores) y A3 (nunca mostrar un traceback) se sostienen.

| Campo | BLINDAJE-01 |
|---|---|
| **ID** | BLINDAJE-01 |
| **Referencia** | `validate_claim_input`, rama 1, `orchestrator.py:62-76`; cadena exacta `f"importe reclamado invalido: {amount_requested!r}"` |
| **Título** | Importe = 0 € desde la UI → Rechazo legible, sin error técnico |
| **Prioridad** | Alta |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" escribe: `Test Blindaje Importe Cero`.<br>6. En el campo "ID Cliente" escribe: `BLINDAJE-01`.<br>7. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>8. En el campo "Importe reclamado (€)" escribe: `0`.<br>9. En el campo "Documentos aportados (tipo)" selecciona: `foto_danys`, `factura`, `denuncia_companyia`.<br>10. Haz clic en el botón "Procesar reclamación".<br>11. Espera a que aparezca el resultado. Comprueba que no hay ningún texto con la palabra "Traceback", "Exception" ni rutas de fichero `.py` visibles en pantalla.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | amount = 0.0 |
| **Resultado esperado** | Tarjeta "Decisión" = `RECHAZO`, leyenda del motivo = `importe reclamado invalido: 0.0`, sin traceback ni mensaje técnico en pantalla |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | BLINDAJE-02 |
|---|---|
| **ID** | BLINDAJE-02 |
| **Referencia** | `validate_claim_input`, rama 3, `orchestrator.py:88-97`; cadena exacta `"nombre del asegurado invalido (vacio o excesivamente largo)"` |
| **Título** | Nombre del asegurado excesivamente largo → Revisión humana legible, sin error técnico |
| **Prioridad** | Media |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. En el campo "Nombre del asegurado" copia y pega este texto de 201 caracteres: `Juan García Fernández López Martínez de la Torre y Sánchez del Río Rodríguez Pérez González Álvarez Domínguez Ruiz Jiménez Moreno Muñoz Álvarez Romero Alonso Gutiérrez Navarro Torres Domingueza`.<br>6. En el campo "ID Cliente" escribe: `BLINDAJE-02`.<br>7. En el desplegable "Tipo de siniestro" selecciona: `Daños propios`.<br>8. En el campo "Importe reclamado (€)" escribe: `2500`.<br>9. En el campo "Documentos aportados (tipo)" selecciona: `foto_danys`, `factura`, `denuncia_companyia`.<br>10. Haz clic en el botón "Procesar reclamación".<br>11. Espera a que aparezca el resultado. Comprueba que no hay ningún texto con la palabra "Traceback", "Exception" ni rutas de fichero `.py` visibles en pantalla.<br>12. Compara con "Resultado esperado".<br>13. Haz una captura de pantalla del resultado. |
| **Datos de prueba** | Nombre de 201 caracteres, ver paso 5 |
| **Resultado esperado** | Tarjeta "Decisión" = `REVISION_HUMANA`, leyenda del motivo = `nombre del asegurado invalido (vacio o excesivamente largo)`, sin traceback |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

| Campo | BLINDAJE-03 |
|---|---|
| **ID** | BLINDAJE-03 |
| **Referencia** | `streamlit_app.py:589-590` (`if not claim_type or amount is None: st.warning(...)`) |
| **Título** | Enviar el formulario sin tipo de siniestro ni importe → aviso de campos obligatorios, no una excepción |
| **Prioridad** | Baja |
| **Tipo** | Adversario |
| **Entorno** | Cloud — navegador |
| **Precondiciones** | Ninguna — solo un navegador con acceso a internet. |
| **Pasos** | 1. Abre en el navegador el link de la app: [URL_APP]<br>2. Espera a que cargue la pantalla "Centro de Gestión de Siniestros".<br>3. En la barra lateral izquierda, haz clic en el botón "Nueva reclamación".<br>4. Baja hasta la sección "O crea una reclamación personalizada".<br>5. Deja "Tipo de siniestro" sin seleccionar (mostrando el texto "Selecciona el tipo…") y "Importe reclamado (€)" vacío.<br>6. No rellenes ningún otro campo.<br>7. Pulsa el botón "Procesar reclamación".<br>8. Observa el mensaje que aparece.<br>9. Compara con "Resultado esperado".<br>10. Haz una captura de pantalla del aviso. |
| **Datos de prueba** | claim_type = None, amount = None |
| **Resultado esperado** | Aviso amarillo con el texto exacto `"Indica al menos el tipo de siniestro y el importe reclamado."` (`streamlit_app.py:590`); no se llega a invocar `process_claim`, no aparece ningún resultado ni traceback |
| **Resultado obtenido** | |
| **Estado** | |
| **Evidencia** | Captura de pantalla |

---

## Tabla resumen final

| ID | Título | Entorno | Prioridad |
|---|---|---|---|
| T1-01 | 32 casos sintéticos, con/sin clave API | Local — terminal | Alta |
| T1-02 | Test automático de determinismo | Local — terminal | Alta |
| T2-01 | 200 importes aleatorios, no-bypass HITL | Local — terminal | Alta |
| T3-01 | RC, 5.000,00 € → PAGO | Cloud — navegador | Alta |
| T3-02 | RC, 5.000,01 € → REVISION_HUMANA | Cloud — navegador | Alta |
| T3-03 | Daños propios, 5.300,00 € → PAGO | Cloud — navegador | Media |
| T3-04 | Daños propios, 5.300,01 € → REVISION_HUMANA | Cloud — navegador | Media |
| T3-05 | RC, 4.999,99 € (borde inferior) → PAGO | Cloud — navegador | Media |
| T4-01 | Falso positivo OFAC "Dimitri Volkoff" | Cloud — navegador | Alta |
| T4-02 | Falso positivo OFAC "Grup Financer Centaure" | Cloud — navegador | Media |
| T4-03 | No-falso-positivo "Ramirez Fuentes" | Cloud — navegador | Media |
| T5.1-01 | OFAC + docs incompletos → INFO_REQUERIDA | Cloud — navegador | Alta |
| T6-01 | Sin clave API → fallback determinista | Local — app con entorno modificado | Alta |
| T6-02 | Clave API inválida → fallback tras fallo | Local — app con entorno modificado | Media |
| T6-03 | RAG desactivado → catálogo determinista | Local — app con entorno modificado | Media |
| T6-04 | Sin clave API + documento real subido | Local — app con entorno modificado | Baja |
| T6-05 | Base de datos caída → resultado igual, sin error | Local — app con entorno modificado | Media |
| T7-01 | Importe 0 € → RECHAZO | Cloud — navegador | Alta |
| T7-02 | Nombre > 200 caracteres → REVISION_HUMANA | Cloud — navegador | Media |
| T7-03 | Sin documentos → INFO_REQUERIDA | Cloud — navegador | Baja |
| T7-04 | Inyección SQL en el nombre → flujo normal, sin bloqueo | Cloud — navegador | Alta |
| T7-05 | Nombre unicode benigno → sin falso positivo OFAC | Cloud — navegador | Media |
| LIBRE-01 | Caso libre feliz → procesado normal | Cloud — navegador | Media |
| LIBRE-02 | Caso libre roto (tipo + importe) → RECHAZO por importe | Cloud — navegador | Alta |
| LIBRE-03 | Caso libre vacío → aviso de campos obligatorios | Cloud — navegador | Baja |
| DEMO-01 | 5 escenarios × 10 repeticiones | Cloud — navegador | Alta |
| BANDEJA-01 | CLM-WA-0001 → PAGO | Cloud — navegador | Alta |
| BANDEJA-02 | CLM-WA-0002 → INFO_REQUERIDA | Cloud — navegador | Media |
| BLINDAJE-01 | Importe 0 sin error técnico | Cloud — navegador | Alta |
| BLINDAJE-02 | Nombre largo sin error técnico | Cloud — navegador | Media |
| BLINDAJE-03 | Formulario incompleto → aviso, no excepción | Cloud — navegador | Baja |

**Total: 31 casos de prueba** (25 de la versión anterior + T3-05 + T7-04 + T7-05 + LIBRE-01/02/03).

---

## Nota de verificación (T2)

El script `backend/scripts/uat_t2_random_amounts.py` se ejecutó el 2026-08-08 (`--n 200 --seed 7`) para confirmar que no está roto antes de entregar este documento. Resultado real obtenido:

```
Casos ejecutados: 200
Fallos (amount > 5000.0 EUR pero decision == PAGO): 0
OK: ningun caso con importe > umbral HITL obtuvo PAGO automatico.
```

Durante la ejecución, la terminal mostró avisos repetidos del tipo `No se han podido persistir las decisiones de UAT-T2-XXXX: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server on 'mariadb'")`. **Esto es esperado y no es un fallo**: es la persistencia best-effort en base de datos (`orchestrator.py:419-441`, ver T6-05) fallando porque no había un MariaDB local arrancado durante esta verificación — el resultado de cada caso se calculó y evaluó igualmente con normalidad, ya que la persistencia está envuelta en un `try/except` que nunca interrumpe el flujo. De hecho, esta ejecución sirve como una confirmación adicional en vivo de T6-05.
