# 3. Herramientas y capacidades del sistema agéntico

## 3.1 Introducción: el papel de las herramientas en un sistema agéntico

En los sistemas de inteligencia artificial basados en agentes, el término *herramienta* (*tool*) designa una función de código que el modelo de lenguaje puede invocar de forma autónoma cuando lo considera necesario para resolver una tarea. Esta capacidad, conocida como *function calling* o *tool use*, transforma al modelo de lenguaje de un generador de texto en un agente capaz de actuar sobre el entorno: consultar bases de datos, ejecutar cálculos, analizar documentos o emitir notificaciones (Anthropic, 2024). El mecanismo es el siguiente: junto con el mensaje del usuario, se expone al modelo una descripción estructurada de cada herramienta disponible —nombre, parámetros y propósito—; el modelo razona sobre cuál invocar y con qué argumentos; el orquestador ejecuta la función y devuelve el resultado para que el modelo continúe su razonamiento. Este ciclo de *razonamiento → acción → observación* sustenta el paradigma ReAct (Yao et al., 2023), que inspira el helper `reason()` empleado en Smart-Claims Agent.

En la implementación concreta del proyecto, las herramientas se definen mediante el decorador `@tool` de LangChain (Chase, 2022), que analiza la firma de la función Python y su *docstring* para construir automáticamente el esquema JSON que se expone al modelo. El código reside principalmente en `backend/app/tools/claim_tools.py` y `backend/app/tools/fraud_tools.py`, y las funciones son invocadas desde los nodos de los agentes del grafo LangGraph.

### 3.1.1 Distinción fundamental: mocks externos frente a capacidades de IA reales

Un aspecto crítico del diseño del prototipo, y que debe quedar explícitamente claro, es que existen **dos categorías conceptualmente distintas** de herramientas y capacidades en el sistema:

**Categoría 1 — Mocks de sistemas externos de Seguros Pepín.** El prototipo Smart-Claims Agent se ha desarrollado sin acceso a los sistemas reales de la empresa. La gestión documental corporativa, el core asegurador, la pasarela de pagos, el CRM y el portal del cliente son sistemas propietarios de Seguros Pepín, S.A. a los que el proyecto académico no tiene conexión. En consecuencia, las herramientas `@tool` que representan estas integraciones son *mocks definitivos*: implementaciones simuladas que reproducen fielmente la interfaz (firma, esquema de entrada y salida) que tendría cada integración en producción, pero cuya lógica interna genera datos sintéticos o deterministas. Estas herramientas son `validate_documents`, `extract_multimodal` (en su rol de fallback), `check_policy` (en su rol de fallback), `approve_payment`, `send_rejection` y `request_more_info`.

**Categoría 2 — Capacidades de IA reales.** Claude no es un sistema de Seguros Pepín: es el LLM propio del proyecto. Tampoco lo son ChromaDB ni el motor antifraude. Por tanto, las capacidades construidas sobre estas tecnologías se implementan de forma real y funcional en el prototipo: la extracción multimodal con Claude Vision (`backend/app/agents/vision.py`), el motor antifraude de cuatro detectores deterministas (`backend/app/tools/fraud_tools.py`) y la base de conocimiento RAG de pólizas basada en ChromaDB (`backend/app/rag/policy_store.py`) son implementaciones reales, no simuladas, que operan en el sistema durante la ejecución.

Esta distinción determina la arquitectura de resiliencia del sistema: cuando la capacidad real no está disponible (sin clave de API, sin ChromaDB inicializado), el sistema cae de forma controlada al mock correspondiente, garantizando que la demostración nunca se interrumpe.

## 3.2 Tabla resumen de herramientas y capacidades

La tabla siguiente ofrece una visión consolidada del catálogo completo del sistema.

| # | Herramienta / Capacidad | Agente principal | Categoría | Propósito |
|---|---|---|---|---|
| 1 | `validate_documents` | B — Validación documental | Mock externo | Verificar documentación aportada y vigencia de la póliza |
| 2 | `extract_multimodal` | C — Extracción multimodal (fallback) | Mock externo | Extracción simulada de datos de documentos (ruta de respaldo) |
| 3 | Claude Vision (`analyze_document`) | C — Extracción multimodal (ruta real) | IA real | Extracción estructurada de imágenes y PDF con Claude Vision |
| 4 | `check_policy` | D — Verificación de cobertura (fallback) | Mock externo | Consulta determinista de cobertura y franquicia |
| 5 | RAG de pólizas (`retrieve_policy`) | D — Verificación de cobertura (ruta real) | IA real | Recuperación semántica de cláusulas de póliza con ChromaDB |
| 6 | Motor antifraude (4 detectores) | G — Fraude y cumplimiento | IA real | Cribado antifraude determinista con scoring compuesto |
| 7 | `approve_payment` | E — Resolución | Mock externo | Emisión simulada de orden de pago al asegurado |
| 8 | `send_rejection` | E — Resolución | Mock externo | Comunicación simulada de resolución denegatoria |
| 9 | `request_more_info` | B — Validación documental | Mock externo | Solicitud simulada de documentación adicional al cliente |

Adicionalmente, `reason()` (`backend/app/agents/reasoning.py`) y el repositorio (`backend/app/db/repository.py`) constituyen módulos de apoyo transversales, no herramientas en el sentido estricto del *function calling*, y se documentan en la sección 3.6.

---

## 3.3 Herramientas `@tool` de LangChain (mocks de sistemas externos)

Las siguientes subsecciones describen cada herramienta definida con el decorador `@tool` en `backend/app/tools/claim_tools.py`. Todas ellas simulan la interfaz de sistemas externos de Seguros Pepín que no están disponibles en el entorno de desarrollo. La estructura de cada subsección cubre: propósito, parámetros de entrada, esquema de salida, agente que la invoca y la proyección de integración real.

### 3.3.1 `validate_documents`

**Propósito.** Verifica que el expediente de reclamación contiene la documentación mínima exigida para el tipo de siniestro declarado y que la póliza asociada se encuentra en vigor. El conjunto de documentos requeridos está centralizado en la constante `REQUIRED_DOCS_BY_TYPE`, compartida entre la herramienta y el Agente B para garantizar una única fuente de verdad.

Los tipos documentales requeridos por tipo de siniestro son:

| Tipo de siniestro | Documentos requeridos |
|---|---|
| `danys_propis` | `foto_danys`, `factura`, `denuncia_companyia` |
| `responsabilitat` | `foto_danys`, `acta_policial`, `dades_tercer` |
| `robatori` | `acta_policial`, `llista_objectes_robats` |
| `danys_mecanics` | `informe_taller`, `factura` |
| `default` | `foto_danys`, `factura` |

**Parámetros de entrada.**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador único del expediente |
| `claim_type` | `str` | Tipo de siniestro (`danys_propis`, `responsabilitat`, `robatori`, `danys_mecanics`, `default`) |
| `doc_types` | `list[str]` | Lista de tipos documentales aportados por el cliente |

**Esquema de salida.**

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `claim_type` | `str` | Tipo de siniestro evaluado |
| `is_valid` | `bool` | Indica si el conjunto documental es suficiente |
| `missing_docs` | `list[str]` | Tipos documentales ausentes |
| `required_docs` | `list[str]` | Lista completa de documentos exigidos |
| `provided_docs` | `list[str]` | Documentos efectivamente aportados |
| `contract_active` | `bool` | Estado de la póliza (siempre `True` en el mock) |
| `checked_at` | `str` | Marca temporal ISO 8601 de la verificación |

**Agente que la invoca.** Nodo B (Validación documental). Si `is_valid` es `False`, el Agente B activa también `request_more_info` para solicitar los documentos faltantes al cliente.

**Mock → Integración real.** En producción, esta herramienta debería dirigirse al **gestor documental corporativo (ECM)** de Seguros Pepín para confirmar la presencia e integridad de los ficheros adjuntos, y al **core asegurador** (sistema de gestión de pólizas) para validar que el contrato estaba activo en la fecha del siniestro declarado. El campo `contract_active` siempre devuelve `True` en el mock, lo que constituye la simplificación más relevante de esta herramienta.

---

### 3.3.2 `extract_multimodal` (fallback del Agente C)

**Propósito.** Esta herramienta actúa como **ruta de respaldo** del Agente C cuando la extracción real mediante Claude Vision no está disponible. Devuelve datos sintéticos plausibles para cada tipo documental reconocido, con una puntuación de confianza generada aleatoriamente en el rango [0,82 – 0,98]. Es importante subrayar que esta herramienta no procesa ningún fichero real: la extracción genuina de imágenes y documentos la realiza la función `analyze_document()` de `backend/app/agents/vision.py` (véase la sección 3.4).

**Parámetros de entrada.**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `file_url` | `str` | URL o ruta del fichero a analizar (no se procesa en el mock) |
| `doc_type` | `str` | Tipo documental (`foto_danys`, `factura`, `acta_policial`, etc.) |

**Esquema de salida.**

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `doc_type` | `str` | Tipo documental procesado |
| `extracted` | `dict` | Datos sintéticos estructurados según el tipo documental |
| `confidence` | `float` | Confianza simulada en [0,82; 0,98] |
| `model` | `str` | Identificador `"claude-sonnet-4-6 (mock)"` |
| `extracted_at` | `str` | Marca temporal de la extracción (ISO 8601) |

**Agente que la invoca.** Nodo C (Extracción multimodal), únicamente como fallback cuando `analyze_document()` devuelve `None`.

**Mock → Integración real.** La ruta real ya existe en el sistema: la función `analyze_document()` invoca a Claude Vision con los ficheros reales del expediente (véase la sección 3.4.1). En producción, la ruta de fallback podría complementarse con un motor de OCR clásico (por ejemplo, Tesseract) para documentos de baja resolución que la VLM no logre interpretar con suficiente confianza.

**Nota sobre `check_fraud`.** El módulo `claim_tools.py` contiene también una función `check_fraud` registrada como `@tool`, que genera un score de riesgo aleatorio en el rango [0,01 – 0,35]. Esta función existía en una versión anterior del sistema, pero el **Agente G ya no la utiliza**: el Agente G emplea exclusivamente el motor antifraude real de cuatro detectores de `fraud_tools.py` (sección 3.5). La función `check_fraud` se mantiene en el módulo por compatibilidad de interfaz, pero no es invocada en el flujo de producción y no debe confundirse con el motor antifraude real.

---

### 3.3.3 `check_policy` (fallback del Agente D)

**Propósito.** Determina si el tipo de siniestro declarado está cubierto por la póliza del asegurado y calcula el importe neto a abonar tras aplicar el límite de cobertura y la franquicia. Esta herramienta actúa como **ruta de respaldo** del Agente D cuando el RAG de pólizas no está disponible. Los parámetros de cobertura están codificados de forma estática en la constante `coverage_rules`, que replica los valores del condicionado de Seguros Pepín con fines de prototipado.

| Tipo de siniestro | Cubierto | Límite máximo | Franquicia | Sección |
|---|---|---|---|---|
| `danys_propis` | Sí | 10 000 € | 300 € | SP-PCS-009 § 3.2 |
| `responsabilitat` | Sí | 50 000 € | 0 € | SP-PCS-009 § 4.1 |
| `robatori` | Sí | 8 000 € | 500 € | SP-PCS-009 § 5.0 |
| `danys_mecanics` | No | — | — | SP-PCS-009 § 7.3 (exclusión) |

**Parámetros de entrada.**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `claim_type` | `str` | Tipo de siniestro |
| `amount` | `float` | Importe reclamado en euros |

**Esquema de salida.**

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `claim_type` | `str` | Tipo de siniestro evaluado |
| `amount_requested` | `float` | Importe reclamado |
| `covered` | `bool` | Indica si el siniestro está amparado |
| `max_coverage` | `float` | Límite máximo de cobertura (€) |
| `deductible` | `float` | Franquicia a cargo del asegurado (€) |
| `net_payable` | `float` | Importe neto a satisfacer: `max(0, min(amount, max_coverage) − deductible)` |
| `policy_section` | `str` | Cláusula o sección de la póliza que ampara la decisión |

**Agente que la invoca.** Nodo D (Verificación de cobertura), únicamente cuando `retrieve_policy()` del RAG devuelve `None`.

**Mock → Integración real.** La ruta real ya existe en el sistema: `retrieve_policy()` realiza una búsqueda vectorial sobre las pólizas indexadas en ChromaDB (sección 3.4.2). En producción, el corpus se alimentaría con los condicionados reales de Seguros Pepín en lugar de los documentos sintéticos de prototipado.

---

### 3.3.4 `approve_payment`

**Propósito.** Emite la orden de pago al asegurado cuando la reclamación ha sido aprobada. Simula la integración con la pasarela de pagos o el core financiero de Seguros Pepín generando un identificador de transacción aleatorio y una fecha de abono programada.

**Parámetros de entrada.**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `amount` | `float` | Importe a abonar (€) |
| `iban` | `str` | Número de cuenta del beneficiario |

**Esquema de salida.**

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `transaction_id` | `str` | Identificador único de transacción (formato `TXN-{claim_id}-{randint}`) |
| `amount` | `float` | Importe abonado (€) |
| `iban_last4` | `str` | Últimos cuatro dígitos del IBAN (trazabilidad sin exponer datos sensibles) |
| `status` | `str` | Estado de la orden (`"scheduled"`) |
| `scheduled_date` | `str` | Fecha prevista de transferencia (estática en el mock) |

**Agente que la invoca.** Nodo E (Resolución), cuando el agente determina que la reclamación es válida, está cubierta y el importe está por debajo del umbral de revisión humana (HITL).

**Mock → Integración real.** En producción, esta herramienta se conectaría a la **pasarela de pagos o al módulo financiero** del core asegurador de Seguros Pepín para emitir una transferencia bancaria real, incluyendo los controles de autorización, firma y reconciliación que exige la operativa aseguradora. El campo `scheduled_date` estático pasaría a calcularse dinámicamente según los plazos regulatorios aplicables.

---

### 3.3.5 `send_rejection`

**Propósito.** Comunica al asegurado la resolución denegatoria de su reclamación, incluyendo una justificación generada por el Agente E y los plazos para ejercer el derecho de reclamación, en cumplimiento con las obligaciones de información de la normativa de seguros.

**Parámetros de entrada.**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `reason` | `str` | Motivo del rechazo, generado por el LLM del Agente E |
| `client_email` | `str` | Dirección de correo electrónico del asegurado |

**Esquema de salida.**

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `email_id` | `str` | Identificador del mensaje (formato `EMAIL-{claim_id}-REJ`) |
| `sent_to` | `str` | Dirección de destino |
| `reason_summary` | `str` | Primeros 200 caracteres del motivo de rechazo |
| `sent_at` | `str` | Marca temporal del envío (ISO 8601) |

**Agente que la invoca.** Nodo E (Resolución), cuando el Agente D ha determinado que el siniestro no está cubierto por la póliza.

**Mock → Integración real.** En producción, la herramienta invocaría el **sistema de notificaciones corporativo o el CRM** de Seguros Pepín para generar y enviar la comunicación por el canal acordado con el cliente (correo electrónico, SMS, área de cliente), con registro de acuse de recibo para fines de cumplimiento normativo.

---

### 3.3.6 `request_more_info`

**Propósito.** Solicita al asegurado que aporte la documentación o información adicional necesaria para continuar con la tramitación, especificando los campos concretos que faltan y el plazo disponible para su presentación (diez días por defecto en el mock).

**Parámetros de entrada.**

| Parámetro | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `missing_fields` | `list[str]` | Lista de campos o tipos documentales ausentes |
| `client_email` | `str` | Dirección de correo electrónico del asegurado |

**Esquema de salida.**

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_id` | `str` | Identificador del expediente |
| `request_id` | `str` | Identificador de la solicitud (formato `INFO-{claim_id}-{randint}`) |
| `fields_requested` | `list[str]` | Campos solicitados (eco de la entrada) |
| `sent_to` | `str` | Dirección de destino |
| `deadline_days` | `int` | Días concedidos al asegurado para responder (`10`) |
| `sent_at` | `str` | Marca temporal del envío (ISO 8601) |

**Agente que la invoca.** Nodo B (Validación documental), cuando `validate_documents` detecta que faltan documentos requeridos.

**Mock → Integración real.** En producción, la herramienta interactuaría con el **portal del cliente de Seguros Pepín** o con el proveedor de correo electrónico transaccional para generar una comunicación personalizada con enlace directo a la sección de carga de documentos, e integraría el seguimiento del estado en el sistema de gestión de expedientes.

---

## 3.4 Capacidades de IA reales

A diferencia de las herramientas de la sección anterior, las capacidades descritas en esta sección están implementadas de forma real y funcional en el prototipo. Son parte del núcleo tecnológico del proyecto y no simulaciones de sistemas externos.

### 3.4.1 Extracción multimodal con Claude Vision (`backend/app/agents/vision.py`)

El Agente C dispone de una capacidad de extracción documental real construida sobre las capacidades de visión del modelo `claude-sonnet-4-6`. La función `analyze_document(data: bytes, media_type: str, filename: str)` recibe el contenido binario de un fichero adjunto, lo codifica en Base64 y lo envía a la API de Claude junto con un *prompt* de extracción estructurado, obteniendo como respuesta un objeto JSON con los campos del expediente.

**Tipos de documento soportados.** La función acepta imágenes en formato PNG, JPEG y WebP, así como documentos PDF. El tipo MIME determina si el bloque multimedia se construye como `"image"` o `"document"` en la solicitud a la API:

```python
if media_type == "application/pdf":
    return {"type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
return {"type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64}}
```

**Esquema de salida.** Claude devuelve un JSON plano que se valida y se enriquece con el nombre del fichero y el identificador del modelo:

| Campo | Tipo | Descripción |
|---|---|---|
| `doc_type` | `str` | Tipo documental reconocido (`factura`, `foto_danos`, `acta`, `informe_taller`, `otro`) |
| `amount` | `float \| null` | Importe en euros detectado, o `null` si no aplica |
| `date` | `str \| null` | Fecha en formato YYYY-MM-DD, o `null` |
| `vendor` | `str \| null` | Emisor, taller o entidad identificada, o `null` |
| `summary` | `str` | Resumen breve en castellano del contenido del documento |
| `confidence` | `float` | Confianza de la extracción entre 0 y 1, autoevaluada por el modelo |
| `filename` | `str` | Nombre del fichero analizado |
| `model` | `str` | Identificador del modelo empleado (`"claude-sonnet-4-6"`) |

**Lógica de degradación controlada.** Si la variable de entorno `ANTHROPIC_API_KEY` no está configurada, o si la llamada a la API falla por cualquier motivo (red, cuota, error de parseo del JSON de respuesta), la función devuelve `None`. El Agente C detecta este valor y cae al mock `extract_multimodal`, garantizando que la demostración no se interrumpe. Esta política de *graceful degradation* es consistente con el resto del sistema.

**Relevancia académica.** Esta implementación constituye el ejemplo más directo del uso de modelos multimodales en el contexto asegurador: permite que el sistema analice automáticamente fotografías de daños, facturas digitalizadas y actas policiales, reduciendo la intervención manual en la fase de instrucción del expediente. La capacidad de visión de los LLM modernos para extraer información estructurada de documentos no estructurados es uno de los avances más significativos de los últimos años en el campo de la automatización de procesos empresariales (Anthropic, 2024).

---

### 3.4.2 RAG de pólizas con ChromaDB (`backend/app/rag/policy_store.py`)

El Agente D puede consultar las condiciones de cobertura de las pólizas mediante un componente de *Retrieval-Augmented Generation* (RAG; Lewis et al., 2020) construido sobre ChromaDB embebido en proceso. Este enfoque permite que el agente recupere la cláusula más relevante para un tipo de siniestro concreto y cite la sección de la póliza que fundamenta su decisión, en lugar de aplicar reglas estáticas.

**Arquitectura del componente.** El módulo `policy_store.py` expone dos funciones principales:

- `_build_collection()`: indexa los documentos de póliza en formato Markdown (con *frontmatter* YAML) alojados en `data/policies/*.md` en una colección ChromaDB embebida en memoria. Cada póliza se representa mediante un texto de indexación conciso anclado en el tipo de siniestro, enriquecido con los metadatos estructurados extraídos del *frontmatter* (`claim_type`, `section`, `covered`, `max_coverage`, `deductible`).

- `retrieve_policy(claim_type: str, description: str)`: realiza una búsqueda vectorial filtrando por el metadato `claim_type` y devuelve la cláusula más relevante. El filtrado combinado (búsqueda semántica + filtro de metadato exacto) garantiza que el resultado corresponde siempre al tipo de siniestro correcto, incluso cuando el corpus crece con múltiples cláusulas por tipo.

**Esquema de salida de `retrieve_policy`.**

| Campo | Tipo | Descripción |
|---|---|---|
| `claim_type` | `str` | Tipo de siniestro de la cláusula recuperada |
| `section` | `str` | Referencia a la sección de la póliza (p. ej., `SP-PCS-009 § 3.2`) |
| `covered` | `bool` | Indica si el siniestro está cubierto según la cláusula recuperada |
| `max_coverage` | `float` | Límite máximo de cobertura en euros |
| `deductible` | `float` | Franquicia aplicable en euros |
| `snippet` | `str` | Fragmento textual de la cláusula recuperada (hasta 280 caracteres) |
| `distance` | `float \| null` | Distancia vectorial entre la consulta y el documento recuperado |

**Control de disponibilidad.** El componente está gestionado por la variable de entorno `SCA_RAG_ENABLED`. Si ChromaDB no está instalado, si el directorio `data/policies/` no existe o si la indexación falla, el módulo registra el fallo en el log y devuelve `None`, activando el fallback determinista `check_policy`. El indicador interno `_load_failed` evita reintentos innecesarios en bucle.

**Naturaleza de las pólizas en el prototipo.** Los documentos indexados son pólizas sintéticas creadas para el prototipo, con estructura de condicionado verosímil y referencias a las secciones del procedimiento SP-PCS-009. En un entorno de producción, estos documentos se sustituirían por los condicionados reales de Seguros Pepín, lo que no requeriría ningún cambio en el código del componente RAG, únicamente en los datos de entrada.

**Fundamento teórico.** El paradigma RAG, introducido por Lewis et al. (2020), combina la capacidad generativa de los LLM con la precisión de los sistemas de recuperación de información, permitiendo que el modelo base sus respuestas en documentos concretos y recuperables en lugar de en conocimiento paramétrico potencialmente desactualizado o incorrecto. En el contexto de la verificación de cobertura aseguradora, esta propiedad es especialmente valiosa: la decisión del Agente D queda fundamentada en una cláusula concreta de la póliza, con trazabilidad directa hacia el documento fuente.

---

### 3.4.3 Motor antifraude de cuatro detectores (`backend/app/tools/fraud_tools.py`)

El Agente G implementa un sistema modular de detección de fraude compuesto por cuatro detectores deterministas y una función de scoring compuesto. A diferencia de enfoques de caja negra, este diseño permite atribuir cada señal de riesgo a una causa concreta y auditable. Los cuatro detectores y la función de scoring residen en `backend/app/tools/fraud_tools.py` y constituyen una implementación real, no un mock.

#### Detector 1 — Verificación OFAC/ONU (`check_ofac_sanctions`)

Verifica el nombre del cliente declarante contra una lista de sanciones financieras que simula la SDN (*Specially Designated Nationals*) de la Oficina de Control de Activos Extranjeros (OFAC) del Departamento del Tesoro de los Estados Unidos y la lista consolidada de sanciones de las Naciones Unidas.

La lista interna `_SANCTIONS_LIST` contiene **15 entidades y personas físicas** sintéticas (ocho con lista `SDN`, siete con lista `ONU`) con nombres plausibles que permiten probar la detección tanto de personas físicas como jurídicas.

El algoritmo emplea *fuzzy matching* mediante `difflib.SequenceMatcher` con normalización previa de caracteres acentuados (conversión NFD + eliminación de diacríticos mediante `unicodedata`) para garantizar que variantes ortográficas como "Amira Belhaj" y "Amira Belhàj" produzcan similitudes equivalentes. El umbral de detección está fijado en **0,82**: una similitud igual o superior a este valor se considera coincidencia positiva y desencadena un veredicto `BLOCKED`.

La función devuelve un `NamedTuple` tipado (`OFACResult`) con los campos: `matched`, `entity_id`, `entity_name`, `similarity` y `sanction_list`.

#### Detector 2 — Anomalía de importe (`check_amount_anomaly`)

Detecta importes estadísticamente anómalos comparando el importe reclamado con los baselines históricos por tipo de siniestro mediante la métrica **Z-score**:

$$Z = \frac{x - \mu}{\sigma}$$

donde $x$ es el importe reclamado, $\mu$ la media histórica y $\sigma$ la desviación típica para el tipo de siniestro. Los baselines de la constante `_AMOUNT_BASELINES` son:

| Tipo de siniestro | Media (€) | Desv. típica (€) | Máximo legítimo (€) |
|---|---|---|---|
| `danys_propis` | 2 800 | 1 400 | 9 000 |
| `responsabilitat` | 12 000 | 8 000 | 48 000 |
| `robatori` | 3 200 | 1 600 | 7 500 |
| `danys_mecanics` | 800 | 400 | 3 000 |
| `_default` | 3 000 | 2 000 | 10 000 |

Un importe se considera anómalo si $|Z| > 2{,}0$ (umbral `_ZSCORE_THRESHOLD`) o si supera el máximo legítimo definido para su tipo. Devuelve `AmountResult` con: `flagged`, `z_score`, `requested`, `mean`, `std` y `exceeded_max`.

#### Detector 3 — Duplicados recientes (`check_duplicate_claims`)

Identifica reclamaciones del mismo cliente y tipo de siniestro dentro de una ventana temporal configurable (90 días por defecto). El detector recibe el historial de reclamaciones previas como parámetro (`existing_claims: list[dict]`), lo que permite pruebas unitarias deterministas sin acceso a la base de datos. En la integración real, este historial se obtendría mediante consulta asíncrona a MariaDB con índice compuesto por `(client_id, claim_type, created_at)`.

Devuelve `DuplicateResult` con: `found`, `matching_claim_ids` y `days_since_last`.

#### Detector 4 — Coherencia documental (`check_document_coherence`)

Analiza las fechas presentes en los datos extraídos de los documentos del expediente buscando inconsistencias temporales. Las comprobaciones implementadas son:

- **Fecha de siniestro futura:** `incident_date > ahora`.
- **Fecha de siniestro excesivamente antigua:** `incident_date < 2015-01-01`.
- **Reclamación previa al siniestro:** `claim_date < incident_date`.
- **Factura anterior al siniestro:** `factura_date < incident_date − 30 días`.

La función soporta múltiples formatos de fecha mediante un parser secuencial (`%Y-%m-%d`, `%d/%m/%Y`, `%Y-%m-%dT%H:%M:%S`, `%Y-%m-%dT%H:%M:%S.%f`). Devuelve `DocCoherenceResult` con: `incoherent` y `issues` (lista de cadenas descriptivas de cada inconsistencia detectada).

#### Scoring compuesto (`compute_risk_score`)

La función `compute_risk_score(ofac, amount, duplicate, doc)` combina los cuatro resultados con pesos calibrados y emite uno de cuatro **veredictos graduados**:

| Fuente de riesgo | Contribución máxima al score |
|---|---|
| OFAC/ONU: coincidencia confirmada | `BLOCKED` inmediato (score = 1,0) |
| Importe: supera el máximo legítimo | +0,40 |
| Importe: Z-score anómalo (sin superar máximo) | hasta +0,35 (proporcional a `\|Z\|`) |
| Duplicados recientes (< 30 días) | +0,35 |
| Duplicados recientes (≥ 30 días) | +0,23 |
| Incoherencia documental | +0,10 por issue detectada (máximo +0,25) |

Los veredictos resultantes son:

| Veredicto | Condición | Consecuencia en el flujo |
|---|---|---|
| `BLOCKED` | Coincidencia OFAC/ONU confirmada | Rechazo automático, flujo terminado |
| `HIGH_RISK` | Score ≥ 0,55 | HITL obligatorio; el supervisor detiene el flujo |
| `MEDIUM_RISK` | Score ≥ 0,25 | HITL recomendado; decisión humana |
| `CLEAR` | Score < 0,25 | Flujo continúa al Agente D |

El campo `is_flagged` del estado del expediente se activa cuando el veredicto es `HIGH_RISK` o `BLOCKED`.

**Mock → Integración real.** En producción, cada detector conectaría con su fuente de datos real:

| Detector | Fuente real proyectada |
|---|---|
| OFAC/ONU | Descarga periódica del fichero SDN oficial de OFAC + lista ONU consolidada de la ONU |
| Anomalía de importe | Cálculo dinámico de $\mu$ y $\sigma$ sobre la tabla `claims` histórica de Seguros Pepín |
| Duplicados | Consulta asíncrona a MariaDB con índice por `(client_id, claim_type, created_at)` |
| Coherencia documental | Datos extraídos por el Agente C mediante Claude Vision (sección 3.4.1) |

---

## 3.5 Estrategia de simulación: mocks definitivos

La decisión de implementar las herramientas de sistemas externos como mocks definitivos —en lugar de mocks temporales o integraciones parciales— responde a cuatro criterios fundamentales:

**Reproducibilidad.** Un sistema agéntico presenta comportamiento no determinista a nivel del razonamiento del LLM, pero el entorno de pruebas debe ser reproducible para validar los caminos de ejecución del grafo. Al controlar los valores de salida de las herramientas, es posible verificar sistemáticamente que cada nodo produce la respuesta esperada ante cada escenario de prueba.

**Independencia de sistemas externos.** El desarrollo del prototipo no puede estar condicionado por la disponibilidad, los tiempos de respuesta o los costes de acceso a los sistemas reales de Seguros Pepín. Los mocks definitivos eliminan esta dependencia y permiten iterar con rapidez durante la fase de investigación.

**Fidelidad de interfaz.** Aunque la lógica interna es simulada, los esquemas de entrada y salida de cada herramienta son idénticos a los que tendría la integración real. Esto garantiza que la sustitución de un mock por su equivalente productivo sea un cambio de implementación interna, sin necesidad de modificar el código de los agentes ni la estructura del grafo.

**Cobertura de escenarios.** El conjunto de mocks cubre todos los caminos de decisión del grafo: reclamación válida y pagada, reclamación rechazada por falta de cobertura, reclamación suspendida por solicitud de documentación, reclamación bloqueada por alerta antifraude y reclamación derivada a revisión humana por importe. Esta cobertura completa es esencial para la evaluación del sistema en el contexto del TFM.

---

## 3.6 Módulos de apoyo transversales

Además de las herramientas y capacidades descritas, el sistema cuenta con dos módulos de apoyo que no son herramientas en el sentido del *function calling*, pero que intervienen de forma transversal en todos los agentes.

### 3.6.1 Helper de razonamiento con CoT (`backend/app/agents/reasoning.py`)

La función `reason(system: str, prompt: str, fallback: str) -> str` encapsula la generación de razonamiento en lenguaje natural mediante Claude. Si la variable de entorno `ANTHROPIC_API_KEY` está disponible, invoca al modelo `claude-sonnet-4-6` a través de `ChatAnthropic` con temperatura 0 para maximizar la consistencia. Si la clave no está configurada o si la llamada falla por cualquier motivo, devuelve el argumento `fallback` —un texto determinista proporcionado por el agente que llama—. Esta dualidad garantiza que la demostración funcione siempre, independientemente de la conectividad, y reduce drásticamente el coste de los tests de integración, que no necesitan emular la red.

### 3.6.2 Repositorio de persistencia (`backend/app/db/repository.py`)

El repositorio centraliza todo el acceso a la base de datos relacional (MariaDB en producción, SQLite en memoria en tests). Los agentes **no acceden directamente a la base de datos**: acumulan sus contribuciones en el campo `decisions_log` del estado compartido del grafo LangGraph durante la ejecución, y la función `process_claim` del orquestador persiste todas las decisiones en una única transacción al finalizar el flujo.

Las funciones principales del repositorio son:

- `save_claim(...)`: inserta un expediente si no existe o actualiza su estado. Operación idempotente y segura ante reintentos.
- `log_agent_decision(claim_id, agent, action, reasoning, confidence, hitl_required)`: materializa en base de datos la decisión de cada agente, incluyendo el texto de razonamiento generado por `reason()`.
- `get_claim_with_decisions(claim_id)`: devuelve el expediente completo con todas sus decisiones en orden cronológico, para su consulta a través de la API REST.
- `list_claims(status, limit, offset)`: lista expedientes con paginación y filtro opcional por estado.

Esta separación entre herramientas (acciones sobre el mundo externo) y persistencia (efecto secundario interno gestionado por el repositorio) sigue el principio de separación de responsabilidades y facilita la sustitución de la base de datos subyacente sin modificar la lógica de los agentes.

---

## 3.7 Tabla consolidada: visión a producción

La tabla siguiente resume el camino de integración proyectado para cada herramienta y capacidad del sistema, ofreciendo una visión de conjunto de los sistemas reales que deberían emplearse en una versión productiva de Smart-Claims Agent.

| Herramienta / Capacidad | Estado en el prototipo | Sistema / Tecnología en producción |
|---|---|---|
| `validate_documents` | Mock externo | ECM de Seguros Pepín + API del core asegurador (verificación de póliza activa) |
| `extract_multimodal` | Mock externo (fallback del Agente C) | Sustituido por Claude Vision en el camino principal; fallback a Tesseract OCR |
| Claude Vision (`analyze_document`) | IA real (gated por `ANTHROPIC_API_KEY`) | Sin cambios; escalado mediante gestión de concurrencia y cuota de la API |
| `check_policy` | Mock externo (fallback del Agente D) | Sustituido por RAG en el camino principal |
| RAG de pólizas (`retrieve_policy`) | IA real (gated por `SCA_RAG_ENABLED`) | Corpus de pólizas reales de Seguros Pepín + ChromaDB persistido (servidor dedicado) |
| Motor antifraude (4 detectores) | IA real (determinista) | Baselines calculados desde BD histórica; OFAC SDN oficial; duplicados contra MariaDB |
| `approve_payment` | Mock externo | Pasarela de pagos / módulo financiero del core asegurador de Seguros Pepín |
| `send_rejection` | Mock externo | CRM / sistema de notificaciones corporativo de Seguros Pepín |
| `request_more_info` | Mock externo | Portal del cliente + proveedor de correo electrónico transaccional |

---

## Bibliografía

Anthropic. (2024). *Tool use (function calling) — Claude API documentation*. https://docs.anthropic.com/en/docs/tool-use

Chase, H. (2022). *LangChain* [Software]. https://github.com/langchain-ai/langchain

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Oguz, B., Riedel, S., & Kiela, D. (2020). *Retrieval-augmented generation for knowledge-intensive NLP tasks*. arXiv:2005.11401. https://arxiv.org/abs/2005.11401

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). *ReAct: Synergizing reasoning and acting in language models*. International Conference on Learning Representations (ICLR 2023). https://arxiv.org/abs/2210.03629
