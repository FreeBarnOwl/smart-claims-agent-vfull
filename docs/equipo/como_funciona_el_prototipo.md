# Cómo funciona el prototipo (para el equipo)

Este documento explica el prototipo de gestión automática de siniestros de seguros que hemos construido para el TFM, sin usar código ni tecnicismos sin explicar. Está pensado para que cualquiera del equipo pueda leerlo en unos 15 minutos y entender qué hace el sistema, qué partes usan IA de verdad y cuáles están simuladas, y qué ha cambiado desde la Entrega 2.

**Regla de oro de este documento:** todo lo que dice viene del código real del repositorio, revisado línea por línea el 2026-08-08. Cuando algo no se ha podido confirmar del todo, aparece marcado como `[VERIFICAR]` en vez de dar por hecho algo que podría no ser cierto. Si en algún momento el código cambia, este documento puede quedarse desactualizado — conviene revisarlo antes de usarlo en la defensa si ha pasado tiempo.

---

## 1. El viaje de una reclamación

Imaginemos que un cliente de la aseguradora tiene un golpe en el coche y presenta una reclamación (en el prototipo, esto se hace rellenando un formulario en la aplicación, o simulando que llega por WhatsApp en la vista "Bandeja"). A partir de ahí, la reclamación pasa por una cadena de "agentes": programas especializados, cada uno con una única responsabilidad, que se van pasando el caso entre sí. Ningún agente se salta pasos ni habla directamente con otro — todos pasan siempre por un **orquestador** central, que decide a quién le toca actuar a continuación. Esto es importante: es el principio de diseño más repetido en la memoria del proyecto, y si alguien del tribunal pregunta "¿un agente puede llamar directamente a otro?", la respuesta correcta es no, nunca — siempre a través del orquestador.

Así se ve el recorrido normal de una reclamación:

```
                    ┌─────────────────────────┐
                    │   Agente A · Orquestador │
                    │  (decide qué toca ahora) │
                    └────────────┬─────────────┘
                                 │
                 ┌───────────────┴────────────────┐
                 │  ¿Importe válido, tipo de       │
                 │  siniestro reconocido, nombre   │
                 │  del cliente correcto?          │
                 └───────────────┬────────────────┘
                          NO ────┤──── SÍ
                          │      │
                    Rechazo o    ▼
                    revisión   ┌─────────────────────────────┐
                    humana     │ Agente B · Validación        │
                    (fin)      │ documental                   │
                               │ ¿Están todos los documentos   │
                               │ necesarios para este tipo de  │
                               │ siniestro?                    │
                               └────────────┬─────────────────┘
                               FALTAN ───────┤──── COMPLETOS
                               │             │
                        Información      ┌───▼──────────────────────────┐
                        requerida        │ Agente C · Extracción         │
                        (fin)            │ multimodal                    │
                                         │ Lee las fotos y documentos     │
                                         │ y extrae los datos clave       │
                                         └────────────┬───────────────────┘
                                                      │
                                         ┌────────────▼───────────────────┐
                                         │ Agente G · Fraude y             │
                                         │ cumplimiento                    │
                                         │ ¿Nombre en listas de sanciones? │
                                         │ ¿Importe anómalo? ¿Duplicado?   │
                                         └────────────┬───────────────────┘
                                         FRAUDE ───────┤──── SIN INDICIOS
                                         │              │
                                   Bloqueo por      ┌───▼──────────────────────┐
                                   fraude (fin)      │ Agente D · Verificación   │
                                                     │ de cobertura              │
                                                     │ ¿La póliza cubre esto?    │
                                                     │ ¿Cuánto correspondería    │
                                                     │ pagar?                    │
                                                     └────────────┬───────────────┘
                                                                  │
                                                     ┌────────────▼───────────────┐
                                                     │ Agente E · Resolución       │
                                                     │ Decide: pago automático,    │
                                                     │ rechazo, o revisión humana  │
                                                     │ si el importe supera el     │
                                                     │ umbral de 5.000 €           │
                                                     └──────────────────────────────┘
```

Puntos importantes de este recorrido, verificados en el código real:

- **El orden real es A → B → C → G → D → E.** Es decir, primero se comprueban los documentos (B) y se extraen los datos (C), y **solo después** se revisa el fraude (G). Esto no siempre fue así — más adelante, en la sección 3, se explica que este orden cambió durante el desarrollo.
- **El flujo se puede cortar antes de llegar al final**, en tres puntos distintos:
  1. Si los datos de entrada no tienen sentido (por ejemplo, un importe negativo, o un tipo de siniestro que no existe en el catálogo), el caso ni siquiera llega al Agente B — se resuelve directamente como rechazo o revisión humana.
  2. Si al Agente B le faltan documentos obligatorios, el caso termina ahí mismo pidiendo la documentación que falta. **El Agente G (fraude) nunca llega a ejecutarse en ese caso** — esto tiene una consecuencia importante que se explica en la sección de blindaje más abajo.
  3. Si el Agente G detecta fraude (por ejemplo, el nombre del cliente coincide con una lista de personas o entidades sancionadas), el caso se bloquea ahí mismo. Los Agentes D y E nunca llegan a ejecutarse — no se calcula ni se paga nada.
- **Nunca hay un pago sin pasar por estas comprobaciones.** El importe final que se pagaría (si corresponde) siempre pasa por el Agente D (que aplica la franquicia y el máximo de la póliza) antes de llegar al Agente E, que es quien decide si el pago es automático o necesita que lo revise una persona.

---

## 2. Las dos preguntas del tribunal

Hay dos preguntas que es casi seguro que el tribunal haga en la defensa, y conviene que todo el equipo sepa responderlas igual.

### Pregunta 1: "¿Esto usa IA de verdad o está todo simulado?"

La respuesta correcta es: **depende de la parte del sistema, y es así a propósito.** El diseño separa dos cosas que en un sistema real de seguros conviene mantener separadas: las **decisiones** (¿se paga o no, cuánto, hay indicios de fraude) son siempre deterministas — es decir, siguen reglas fijas y dan siempre el mismo resultado con los mismos datos, sin usar ningún modelo de lenguaje (LLM, el tipo de inteligencia artificial detrás de asistentes como Claude o ChatGPT). Lo que sí puede usar un LLM real es el **texto explicativo** que acompaña a cada decisión, y la **lectura de documentos** cuando el usuario sube fotos o PDFs reales.

Con eso en mente, esto es lo que usa IA real (Claude) y lo que es determinista, agente por agente:

- **Agente G (fraude):** completamente determinista. Compara el nombre del cliente con una lista de personas/entidades sancionadas usando una fórmula de similitud de texto (no un LLM), revisa si el importe se sale de lo habitual para ese tipo de siniestro con una fórmula estadística, comprueba si hay una reclamación muy parecida en los últimos 90 días, y compara fechas entre documentos. Ninguna de estas cuatro comprobaciones usa un modelo de lenguaje — solo el texto que explica el resultado puede generarse con IA real si hay clave de acceso disponible.
- **Agente E (resolución):** también completamente determinista — decide con una regla de umbral fija (si el importe a pagar supera 5.000 €, pasa a revisión humana en vez de pagarse automáticamente).
- **Agente B (validación documental):** determinista — compara la lista de documentos aportados contra la lista de documentos obligatorios para ese tipo de siniestro.
- **Agente C (extracción de documentos):** aquí sí hay IA real de verdad — si el usuario sube una foto o un PDF real, el sistema usa Claude con capacidad de visión para leer el documento y extraer los datos. Si no se sube ningún archivo real, usa datos simulados en su lugar, según el tipo de documento declarado.
- **Agente D (verificación de cobertura):** puede usar una técnica llamada RAG (te lo explico en un momento) para consultar el texto real de las pólizas, o si eso no está disponible, cae automáticamente a una tabla de reglas fija con los importes de cobertura y franquicia por tipo de siniestro.
- **Agente F (conciliación, ver su ficha completa en la sección 5):** completamente determinista, por decisión explícita del equipo — más detalles en la sección 3.

**RAG** significa "generación aumentada por recuperación" — en la práctica, es una forma de que el sistema busque primero el fragmento de texto relevante (aquí, el texto real de la póliza) y luego lo use para responder con más precisión, en vez de "inventar" la respuesta de memoria.

`[VERIFICAR]`: dentro de la propia aplicación hay una pantalla ("Arquitectura") que en un sitio describe el RAG de pólizas como una integración simulada, aunque en la práctica está activado por defecto y es una capacidad real. Si alguien del tribunal ve esa pantalla y pregunta por esta aparente contradicción, la respuesta correcta es la de este documento: el RAG es una capacidad real que se activa por defecto, con una tabla de reglas fija como reserva si no está disponible.

### Pregunta 2: "¿Qué pasa si la IA falla o no hay conexión?"

Esta pregunta es clave porque, en la propia defensa, puede fallar el wifi del aula. La respuesta corta es: **nada se rompe, el sistema sigue funcionando con reglas fijas, y nunca se le muestra a nadie un mensaje de error técnico en pantalla.**

En detalle, esto es lo que pasa en cada punto donde el sistema podría depender de una IA externa:

- **Si no hay clave de acceso a la IA configurada, o la llamada falla por cualquier motivo** (sin conexión, tiempo de espera agotado, respuesta inesperada): el sistema usa automáticamente un texto explicativo genérico ya preparado de antemano, en vez del texto generado por IA. La decisión (pagar, rechazar, pedir revisión) **no depende nunca de si esto funciona o no** — solo cambia el texto que explica el porqué.
- **Si el usuario sube una foto o documento real y la lectura con IA falla:** el sistema no se cae; sustituye la lectura por un registro neutro que indica "extracción no disponible" y sigue el proceso con datos limitados en vez de bloquear el caso.
- **Si la consulta al texto de las pólizas (RAG) no está disponible:** el Agente D cae automáticamente a la tabla de reglas fija de cobertura, sin que el usuario note ninguna interrupción.
- **Si ocurre cualquier error interno inesperado, de cualquier tipo, en cualquier punto del proceso:** hay una red de seguridad general alrededor de todo el recorrido que detecta ese error, nunca deja que se vea un mensaje técnico en pantalla, y en su lugar deriva el caso a revisión humana con una explicación entendible. Esto está probado con pruebas automáticas específicas y es, según las propias notas técnicas del proyecto, la pieza de blindaje con mayor beneficio de todas las implementadas.
- **Si la base de datos no está disponible en el momento de guardar el resultado:** el resultado se le sigue mostrando con normalidad al usuario; solo falla el guardado en el histórico, y ese fallo queda registrado para el equipo técnico, nunca visible para quien está usando la aplicación.

En resumen: cualquier pieza que dependa de un servicio externo (IA de texto, IA de visión, búsqueda en pólizas, base de datos) tiene una alternativa de reserva que garantiza que el sistema siempre termina dando una respuesta legible, nunca un fallo en pantalla.

---

## 3. Qué cambió respecto a la Entrega 2

Los capítulos de la memoria de la Entrega 2 (arquitectura, herramientas, manual de usuario, evaluación) se escribieron y cerraron el 25 de junio de 2026. Desde entonces ha habido un cambio importante que el equipo debe conocer, sobre todo quien esté escribiendo o revisando la parte de la memoria que menciona el Agente F.

### El Agente F cambió de propósito

En el diseño original (Entrega 1), el Agente F estaba pensado para predecir, usando aprendizaje automático (Machine Learning), qué reclamaciones acabarían "judicializándose" (es decir, yendo a juicio), sobre la base de una previsión de unos 1.000 casos al año. El 21 de julio de 2026, el cliente real del proyecto corrigió ese dato: en la práctica, solo se judicializan unos 10 expedientes al año — el 0,08% de los 12.000 siniestros que gestiona la aseguradora. Con un volumen tan bajo, no hay datos suficientes para entrenar un modelo de Machine Learning fiable, así que el 8 de agosto de 2026 el equipo decidió cambiar el enfoque del Agente F.

En vez de predecir judicialización, el Agente F pasó a ser un **asistente de conciliación**: una herramienta de apoyo para el equipo que negocia con clientes que ya han rechazado una primera oferta de indemnización. El nuevo Agente F sigue reglas fijas (no usa Machine Learning ni IA) para recomendar el siguiente paso — por ejemplo, subir la oferta a un cierto porcentaje del importe reclamado, o avisar si un caso lleva mucho tiempo sin respuesta del cliente. Como cualquier otro agente del sistema, el Agente F solo **recomienda** — nunca ejecuta nada por su cuenta; la decisión final y su ejecución las toma siempre una persona.

Una diferencia importante frente a los demás agentes: el Agente F **no forma parte del recorrido automático A → B → C → G → D → E** descrito en la sección 1. Es un módulo aparte, con su propia pantalla de demostración en la aplicación, pensado para mostrar cómo podría funcionar esta ayuda a la conciliación — no está conectado al flujo principal de resolución de siniestros porque ese flujo principal no incluye, de momento, una fase de negociación tras un primer rechazo.

### El "blindaje" de entrada (validación y manejo de errores)

Durante el desarrollo se ha ido reforzando el sistema contra entradas inesperadas o fallos internos — a esto el equipo se refiere internamente como "blindaje". A fecha de este documento, estas son las piezas ya implementadas y verificadas con pruebas automáticas:

- Validación de que el importe reclamado, el tipo de siniestro y el nombre del cliente tienen sentido antes de procesar nada.
- Una red de seguridad general que evita que cualquier error interno inesperado se muestre en pantalla, derivando el caso a revisión humana en su lugar.
- La garantía, ya explicada en la sección 2, de que ningún mensaje técnico de error llega nunca a la pantalla del usuario.
- Un tiempo máximo de espera para las llamadas a la IA, con reserva automática a texto fijo si se agota.

`[VERIFICAR]`: en la planificación interna del equipo se había previsto además un panel de "caso libre" en la aplicación, pensado para poder introducir un caso improvisado si el tribunal pide probar algo fuera de los escenarios preparados. A fecha de este documento **no se ha encontrado ese panel implementado en el código** — no debe darse por hecho que existe hasta que se confirme lo contrario.

---

## 4. Chuleta de una página

Para tener a mano durante la defensa, sin tener que buscar en el resto del documento:

**El recorrido de una reclamación:** A (orquestador) → B (documentos) → C (lectura de documentos) → G (fraude) → D (cobertura) → E (resolución). El orden importa: los documentos se revisan antes que el fraude, y el fraude se revisa antes que la cobertura y el pago.

**Los cinco posibles resultados de una reclamación:**
- Pago aprobado automáticamente.
- Rechazo (por ejemplo, ese tipo de daño no está cubierto por la póliza).
- Rechazo por fraude (el Agente G bloquea el caso).
- Revisión humana requerida (el importe a pagar supera 5.000 €, o hay algo en los datos de entrada que no encaja del todo pero podría ser legítimo).
- Información requerida (faltan documentos obligatorios para ese tipo de siniestro).

**Los números clave que hay que tener memorizados:**
- **5.000 €** — a partir de este importe (sin llegar a incluirlo: exactamente 5.000 € sigue siendo pago automático), el sistema exige revisión humana en vez de pagar solo.
- **0,82 sobre 1** — el nivel de parecido de texto necesario entre el nombre de un cliente y una entidad de la lista de sanciones para que el sistema lo marque como posible coincidencia. No hace falta que el nombre sea idéntico.
- **90 días** — la ventana de tiempo en la que el sistema busca reclamaciones muy parecidas ya presentadas, para detectar posibles duplicados.
- **~20 segundos** — el tiempo máximo que el sistema espera una respuesta de la IA antes de usar el texto de reserva.

**Por qué B va antes que G (documentos antes que fraude):** si a un cliente que resulta estar en la lista de sanciones le faltan documentos, el sistema le pedirá la documentación que falta en vez de bloquearlo directamente por fraude — porque el Agente G nunca llega a ejecutarse si el Agente B ya cortó el proceso antes. Esto es una decisión de diseño conocida y documentada, no un error: en ningún caso se paga nada, así que no hay riesgo económico, aunque conviene saber explicarlo si el tribunal lo pregunta.

**Qué usa IA real y qué no, en una frase:** las decisiones (pagar, rechazar, marcar como fraude) nunca dependen de un modelo de lenguaje; solo el texto explicativo y la lectura de documentos/pólizas pueden usar IA real, y ambas tienen una alternativa fija si la IA no está disponible.

**Términos que pueden salir en la defensa:**
- **IA / LLM (modelo de lenguaje):** el tipo de inteligencia artificial capaz de generar texto, como Claude. En este proyecto se usa solo para explicaciones y lectura de documentos, nunca para decidir.
- **RAG:** técnica en la que el sistema busca primero el texto relevante (aquí, el de la póliza) y lo usa para responder, en vez de inventar la respuesta.
- **HITL (Human In The Loop, "humano en el bucle"):** cualquier punto en el que el sistema, en vez de decidir solo, deriva el caso a una persona.
- **Fallback (reserva):** el comportamiento alternativo que se activa automáticamente cuando algo falla (sin conexión, IA no disponible, etc.), para que el sistema nunca se quede sin respuesta.
- **OFAC:** siglas de la oficina estadounidense que publica listas de personas y entidades sancionadas; el sistema usa una lista de ejemplo con ese mismo espíritu para simular ese tipo de comprobación.
- **Blindaje:** el conjunto de medidas del sistema para que nunca se rompa ni muestre un error técnico ante una entrada inesperada.
- **Agente / nodo:** cada uno de los programas especializados (A, B, C...) que forman el sistema; técnicamente cada uno es un "nodo" dentro del grafo que dirige el orquestador.

---

## 5. Fichas de los agentes

Cada ficha usa el nombre exacto que aparece en la propia aplicación.

### Agente A · Orquestador

Es el director de orquesta del sistema. No toma decisiones sobre el siniestro en sí — su trabajo es recibir la reclamación, comprobar que los datos de entrada tienen sentido, y decidir en cada momento a qué agente le toca actuar a continuación, según lo que ya se sabe del caso. Es también el único punto por el que pasan todas las comunicaciones entre agentes — ninguno de los demás agentes se llama entre sí directamente.

### Agente B · Validación documental

Comprueba que la reclamación tiene todos los documentos obligatorios para ese tipo de siniestro (por ejemplo, para un robo hacen falta el atestado policial y la lista de objetos robados; para daños propios, la foto del daño, la factura y la denuncia a la compañía). Si falta algo, el caso se detiene ahí mismo pidiendo la documentación que falta, y ningún agente posterior llega a ejecutarse.

### Agente C · Extracción multimodal

Lee los documentos aportados y extrae de ellos los datos relevantes (tipo de documento, importe, un resumen). Si el usuario ha subido una foto o un PDF real, esta lectura la hace una IA con capacidad de visión de verdad; si no se ha subido nada real, usa datos simulados según el tipo de documento indicado.

### Agente D · Verificación de cobertura

Comprueba si la póliza del cliente cubre ese tipo de siniestro, y si es así, calcula cuánto correspondería pagar aplicando el máximo de cobertura y la franquicia (la parte que el cliente asume de su bolsillo). Cuando está disponible, consulta el texto real de las pólizas mediante RAG; si no, usa una tabla de reglas fija con los importes por tipo de siniestro.

### Agente E · Resolución

Toma la decisión final sobre el siniestro, a partir de lo que han encontrado los agentes anteriores: si la póliza no cubre el daño, rechaza; si lo cubre y el importe a pagar no supera los 5.000 €, aprueba el pago automáticamente; si lo supera, deriva el caso a revisión humana en vez de pagar solo.

### Agente G · Fraude y cumplimiento

Revisa cuatro señales de posible fraude o incumplimiento normativo antes de que se calcule ningún pago: si el nombre del cliente coincide (aunque sea de forma parecida, no solo exacta) con una lista de personas o entidades sancionadas; si el importe reclamado se sale de lo habitual para ese tipo de siniestro; si hay una reclamación muy similar presentada en los últimos 90 días; y si las fechas entre los distintos documentos aportados son coherentes entre sí. Si detecta algo, bloquea el caso ahí mismo — ni el Agente D ni el E llegan a ejecutarse.

### Agente F · Asistente de conciliación

Este es el agente que más ha cambiado durante el proyecto (ver sección 3 para el porqué). Su trabajo actual es ayudar al equipo que negocia con clientes que ya han rechazado una primera oferta de indemnización, recomendando el siguiente paso a seguir: por ejemplo, subir la oferta a un porcentaje mayor del importe reclamado, esperar la respuesta del cliente, o avisar si un caso lleva demasiado tiempo estancado sin respuesta o sin resolverse. Cuando el cliente ya ha rechazado la oferta más alta prevista, el Agente F no decide por su cuenta qué hacer a continuación — presenta varias opciones para que una persona elija.

A diferencia de los demás agentes, el Agente F **no forma parte del recorrido automático** A → B → C → G → D → E de la sección 1: es un módulo independiente, con su propia pantalla de demostración dentro de la aplicación, y sigue reglas fijas sin usar ningún modelo de IA. En cada recomendación que hace, el sistema deja explícito que la decisión y su ejecución le corresponden siempre a una persona — el agente solo aconseja.

### Agente H — *(sin implementar)*

El catálogo original de agentes del proyecto (Entrega 1) contemplaba un octavo agente, pensado como un asistente legal de apoyo para expedientes que ya han llegado a la vía judicial. `[VERIFICAR — confirmado a fecha de este documento]`: el Agente H **no se ha llegado a implementar** en ningún momento del proyecto — no existe como código, ni como parte de la aplicación, ni como módulo independiente como sí lo es el Agente F. Se menciona en la documentación del proyecto únicamente como algo reservado para una fase posterior, fuera del alcance de esta entrega. Por eso la numeración de los agentes salta de la E a la G: las letras F y H se reservaron desde el principio para estas dos piezas adicionales, y de las dos, solo el Agente F ha llegado a tener una versión funcional en este prototipo.
