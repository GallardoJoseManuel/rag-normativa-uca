# Diario de desarrollo

Registro de lo que hago en cada sesión, las decisiones que tomo y por qué,
y los problemas que encuentro.

---

## Apuntes generales: qué es un RAG

**RAG** (*Retrieval-Augmented Generation*, generación aumentada con recuperación): en lugar
de pedirle a un LLM que responda de memoria, primero se **buscan** los fragmentos de los
documentos relacionados con la pregunta y se le pasan junto a ella. El LLM responde
**leyendo** esos fragmentos, no recordando.

Por qué no basta con preguntarle al LLM directamente:
- No conoce la normativa de la UCA, o la conoce a medias o desactualizada (las
  modificaciones de 2014 y 2015).
- Cuando no sabe algo, puede inventarse una respuesta que suena convincente
  (*alucinación*). Con los fragmentos delante, se le puede exigir que responda solo con
  ellos, que cite el artículo y que diga "no lo sé" si no está.
- Reentrenar un modelo con los documentos (*fine-tuning*) es caro, hay que repetirlo cada
  vez que cambia la norma y no permite citar la fuente. Con un RAG basta con reindexar.

Tiene dos fases:

```
INDEXACIÓN (una vez, o cuando cambian los documentos)
PDFs → texto limpio → artículos → versión vigente → chunks → embeddings → base vectorial
        (paso 2)                                    (paso 3)  (paso 5)

CONSULTA (cada pregunta)
pregunta → embedding → k chunks más parecidos → prompt (pregunta + chunks) → LLM → respuesta con citas
                       (paso 6: recuperación)                              (paso 7: generación)
```

Hay **dos modelos distintos**: el de embeddings (pequeño, local, solo convierte texto en
vectores, sirve para buscar) y el LLM (grande, genera el texto de la respuesta). El LLM
puede ser local (por ejemplo con Ollama) o por API (por ejemplo Claude); el proyecto lo
dejará intercambiable.

La calidad del RAG depende sobre todo de la **recuperación**: si el artículo correcto no
llega al LLM, no hay respuesta buena posible. Por eso los pasos 3 a 6 (troceado,
evaluación, indexación, recuperación) son el núcleo del proyecto, y por eso cada decisión
se mide con el conjunto de evaluación.

---

## 2026-11-24 · Sesión 1: configuración del proyecto

### Qué he hecho
- Creo el repositorio `rag-normativa-uca` en GitHub y lo clono en mi carpeta de desarrollo.
- Creo un entorno virtual (`.venv`) para el proyecto.
- Instalo PyMuPDF y creo el `requirements.txt`.
- Configuro el `.gitignore` para no subir los documentos originales.
- Reúno un corpus inicial de 7 documentos y los registro en `data/sources.csv`.

### Decisiones
- **Licencia MIT**: es permisiva y la más habitual en proyectos personales. Cubre mi
  código, no los documentos de la UCA.
- **Un entorno virtual propio** para evitar conflictos
  de versiones y que `requirements.txt` refleje solo lo que usa este proyecto.
- **`requirements.txt` escrito a mano** con versiones fijadas (`pymupdf==2.1`), solo
  con las dependencias directas, en lugar de usar `pip freeze`.
- **PyMuPDF tiene licencia AGPL-3.0.** La mantengo porque el repositorio es público y
  abierto, así que cumplo con publicar el código. Alternativas permisivas si hiciera
  falta: `pypdf` (BSD) o `pdfplumber` (MIT).
- **Los PDFs no se suben al repositorio** (`data/raw/*` en el `.gitignore`), porque
  tienen sus propios derechos. Para que sea reproducible, `data/sources.csv` guarda la
  URL de cada uno. Mantengo la carpeta con `.gitkeep`.
- **Corpus inicial de 7 documentos** (unas 60 páginas): basta para construir y evaluar
  el pipeline. Ampliarlo más adelante puede ser un experimento por sí mismo.

### Problemas y soluciones
- **PowerShell no dejaba activar el entorno** ("la ejecución de scripts está
  deshabilitada"). Solución: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`,
  que permite scripts locales solo para mi usuario.
- **Excepción en el `.gitignore`**: `data/raw/` con `!data/raw/.gitkeep` no funciona,
  porque Git no mira dentro de una carpeta ignorada. Hay que usar `data/raw/*`.

---

## 2026-11-24 · Sesión 2: análisis exploratorio de los documentos

### Análisis manual

| Documento | Págs. | Estructura | Ruido | Tablas o listas | Relación con otros | Utilidad |
|---|---|---|---|---|---|---|
| reglamento_marco_tfg_uca_2012 | 9 | Cabecera del acuerdo del Consejo de Gobierno (p. 1), título y preámbulo largo (p. 2-3), 10 artículos (p. 3-9), disposición adicional y final (p. 9). Artículos con formato **inconsistente**: `Artículo 1.º.`, `Art. 2.º.`, `Art. 4.º` (sin punto final), `Art. 10.` (sin º). Apartados numerados `1.`, `2.`... | Poco ruido visible: la cabecera del BOUCA (`Pág. 16 Viernes 27 Julio 2012 BOUCA Nº 148`) solo aparece en la p. 1. No hay membrete ni números de página. Ruido invisible: 63 caracteres de control `\x03` | No hay tablas. Listas numeradas dentro de los artículos | Modificado por tfg_uca_2014, que añade artículos y **renumera** el 9 y el 10 como 14 y 15. Lo desarrolla tfgm_esi | **Media-alta**: norma general de la UCA. El reglamento de la ESI concreta casi todo, pero este es la base. El preámbulo (p. 2-3) aporta contexto, no respuestas prácticas |
| modificacion_reglamento_tfg_uca_2014 | 4 | Justificación (p. 1-2) y modificaciones numeradas `PRIMERO.`, `SEGUNDO.`... (p. 2-4). Añade un **Capítulo II** con artículos nuevos 9 a 13 (dobles títulos), renumera los antiguos 9 y 10 como 14 y 15, y añade frases sueltas a los artículos 2.º y 6.º | Membrete del Vicerrectorado de Docencia (9 líneas: dirección, teléfono, fax, web, correos) repetido en las 4 páginas | No hay tablas | Modifica tfg_uca_2012. Ordena elaborar un "texto refundido" que no está en el corpus | **Media**: solo afecta a dobles títulos y a dos frases sueltas. Pero es crítica para la coherencia: su `Art. 9.º` no es el mismo que el `Art. 9.º` de 2012 |
| reglamento_tfgm_esi | 17 | Portada (p. 1), historial de revisiones (p. 2-3), índice (p. 3-4), preámbulo y 25 artículos agrupados en 8 bloques con título en mayúsculas (p. 4-13), disposiciones adicional y transitoria (p. 14), anexos con modelos de portada (p. 15-17). Artículos marcados como `Artículo N. Título.` en su propia línea; dentro, apartados `a)`, `b)`... | Membrete de la ESI (logo + dirección) y `pág. N` en todas las páginas. Notas al pie numeradas pegadas al texto ("...to.2") | Tabla del historial de revisiones (p. 2-3) con viñetas dentro de celdas. Listas de apartados en casi todos los artículos | Desarrolla el Reglamento marco UCA/CG07/2012 y su modificación de 2014 (los cita en el preámbulo) | **Alta**: es la norma más concreta para estudiantes de la ESI. Útiles las p. 4-14; portada, historial, índice y anexos aportan poco o nada |
| calendario_tfgm_esi_2026_27 | 1 | Calendario visual del curso 2026-27: 12 meses en cuadrícula, con los días marcados por colores y una leyenda (fecha límite de subida, reunión de la comisión, periodo de defensa, festivo) | Todo es formato visual: 84 elementos de dibujo (los colores) | PyMuPDF detecta 9 tablas (las cuadrículas de los meses) | Complementa tfgm_esi (fechas concretas de los procedimientos) | **Alta para el usuario, nula tal cual**: la información está en los colores y el texto extraído es una lista de números sin sentido |
| rubrica_evaluacion_tfg_esi | 2 | Una tabla de 11 filas x 8 columnas: aspecto evaluado, 5 rangos de nota con su descripción y columna para el tribunal (p. 1). Línea para la valoración individual (p. 2) | Espacios no separables (`\xa0`) en lugar de espacios normales | **Todo es tabla**. `find_tables()` la detecta, pero pega las palabras ("Muydeficiente", "Valorentre3y<de5puntos") | Complementa los artículos de evaluación de tfgm_esi. Es de la convocatoria de septiembre de 2014 | **Media**: responde a "¿qué se valora en el TFG?", pero hay que convertir la tabla a texto con sentido |
| reglamento_practicas_externas_uca_2012 | 22 | Cabecera del acuerdo (p. 1), preámbulo (p. 2-3), **índice completo** (p. 3-5), cuerpo con 4 títulos, capítulos y 56 artículos (p. 6-22) y disposiciones adicionales, transitorias, derogatoria y finales (p. 21-22). Artículos uniformes: `Artículo N.º Título.-` (1-9) y `Artículo N. Título.-` (10-56). Apartados `1.`, `a)`, `i.` | Cabecera del BOUCA solo en la p. 1 (las otras menciones al BOUCA son citas dentro del texto). Sin membrete repetido | No hay tablas. Muchas listas anidadas (`1.` → `a)` → `i.`) | Modificado por practicas_uca_2015, que reescribe 15 artículos. Su índice no coincide del todo con el cuerpo ("CAPÍTULO V. PREMIOS" en el índice frente a "CAPÍTULO VI" en el cuerpo) | **Alta**: es la norma completa de prácticas, pero un 25-30 % de sus artículos han cambiado en 2015 |
| modificacion_reglamento_practicas_uca_2015 | 7 | Cabecera del BOUCA (p. 1), justificación (p. 2-3) y modificaciones de la forma "el artículo N queda redactado como sigue: <<texto nuevo>>" (p. 3-6). Disposición final (p. 6) | **La p. 7 es otro acuerdo del boletín** (designación de miembros de la Comisión de Prácticas), que no forma parte de la modificación | No hay tablas | Modifica practicas_uca_2012: artículos 6, 13, 14, 17, 22, 23, 24, 26, 31, 37, 38, 39, 51, 52 y 54 | **Alta**: tiene la redacción vigente de esos 15 artículos. El texto nuevo está delimitado por `<<` y `>>`, así que se puede extraer |

### Lo que ve el programa (extracción con PyMuPDF)

#### reglamento_tfgm_esi 
- **Orden del texto**: correcto en el cuerpo, que está a una columna. Cada página empieza
  por el membrete, la dirección y `pág. N` antes del contenido.
- **Encabezados y pies de página**: el membrete sale como texto en las 15 primeras páginas
  ("Escuela Superior de Ingeniería / Dirección / Avda. Universidad de Cádiz, 10 / ...").
  Si no lo limpio, ese texto aparecerá repetido en muchos chunks.
- **Guiones y saltos de línea**: no hay palabras partidas con guion al final de línea, pero
  cada línea visual termina en salto de línea aunque la frase siga. Habrá que unir las
  líneas de un mismo párrafo. Las notas al pie aparecen pegadas a la palabra ("...to.2").
- **Tablas**: el historial de revisiones sale como una lista de celdas sueltas, una por
  línea (número, fecha, modificación...), y se pierde la relación entre columnas.
- **Índice**: aparece con el mismo formato que los títulos reales (`Artículo 1.` /
  `Objeto.` / `4`), pero partido en líneas. Si busco artículos con un patrón, tengo que
  saltarme el índice para no detectarlos dos veces.
- **Anexos**: las portadas de ejemplo extraen un TFG de ejemplo (título, autor y tutor
  ficticios). Es texto que podría confundir al RAG.
- **Artículos**: en el cuerpo, `Artículo N. Título.` sale en una sola línea; con la
  expresión regular `^Artículo \d+` detecto los 25. Algunos son largos (el 22 ocupa
  unas 3 páginas).

#### reglamento_marco_tfg_uca_2012
- **Orden del texto**: correcto, a una columna.
- **Encabezados y pies**: solo la cabecera del BOUCA en la p. 1. Es el documento más
  limpio a la vista.
- **Caracteres invisibles**: 63 caracteres de control `\x03` al final de títulos y
  párrafos. No se ven en el visor de PDF, solo en el texto extraído.
- **Artículos**: el patrón `^Artículo \d+` solo detecta el artículo 1. Los demás empiezan
  por `Art. N.º`, con variaciones de puntuación (`Art. 2.º.`, `Art. 4.º`, `Art. 10.`).
  Hace falta un patrón más flexible, por ejemplo `^(Artículo|Art\.)\s*\d+`.
- **Saltos de página**: varios artículos empiezan en una página y siguen en la siguiente
  (el 4, el 6, el 7 y el 8). Hay que unir el texto de todo el documento **antes** de trocear.

#### modificacion_reglamento_tfg_uca_2014
- **Encabezados**: el membrete del Vicerrectorado (9 líneas) se repite en las 4 páginas.
  Mi script lo detecta como "líneas que aparecen en muchas páginas".
- **Estructura**: no es un reglamento completo, sino instrucciones de cambio
  ("PRIMERO. ADICIÓN DE UN CAPÍTULO...", "TERCERO. Se modifica el párrafo cuarto del
  artículo 6.º..."). Algunas añaden artículos enteros y otras solo una frase.
- **Conflicto de numeración**: añade un nuevo `Art. 9.º` (dobles títulos) y renumera el
  antiguo 9 como 14. Si indexo los dos documentos tal cual, habrá dos "artículo 9" del
  mismo reglamento con contenido distinto.

#### calendario_tfgm_esi_2026_27
- **Texto extraído**: días de la semana (`L M M J V S D`) y números del 1 al 31 sin
  ningún orden útil, más la leyenda y los nombres de los meses al final.
- **Por qué**: la información (qué día es cada cosa) está en el color de las celdas, que
  PyMuPDF extrae como 84 dibujos, no como texto.

#### rubrica_evaluacion_tfg_esi
- **`get_text()`**: mantiene las palabras, pero las celdas salen en orden de lectura,
  mezcladas, y con espacios no separables (`\xa0`).
- **`find_tables()`**: detecta la tabla (11 x 8) y respeta las filas y columnas, pero
  pierde los espacios entre palabras ("Muydeficiente").
- Ninguna de las dos opciones da texto listo para el RAG. Habría que reconstruir cada fila
  como una frase ("Bibliografía: entre 5 y 7 puntos si es suficiente pero mejorable...").

#### reglamento_practicas_externas_uca_2012
- **Índice**: las p. 3-5 repiten los títulos de los 56 artículos. Mi script los detecta
  dos veces (índice y cuerpo), lo mismo que en el reglamento de la ESI.
- **Encabezados**: solo la cabecera del BOUCA en la p. 1. "BOUCA" aparece en otras
  páginas, pero son citas dentro del texto, no cabeceras. Ojo al limpiar por palabras clave.
- **Artículos**: formato uniforme (`Artículo N.º Título.-` y `Artículo N. Título.-`), así
  que el patrón flexible los detecta todos.
- **Jerarquía**: TÍTULO → CAPÍTULO → Artículo → apartados `1.` / `a)` / `i.`. El título y
  el capítulo son buenos metadatos.

#### modificacion_reglamento_practicas_uca_2015
- **Estructura**: frases del tipo "el artículo 13 queda redactado como sigue:" seguidas
  del texto nuevo entre `<<` y `>>`. Se puede extraer automáticamente qué artículo cambia y
  cuál es su redacción nueva.
- **Contenido ajeno**: la p. 7 es otro acuerdo del mismo boletín. Hay que descartarla.

### Cómo lo he comprobado
Script de exploración ([`scripts/explorar_pdfs.py`](../scripts/explorar_pdfs.py), se
ejecuta con `python scripts/explorar_pdfs.py`) que, para cada PDF, recorre las páginas con
PyMuPDF y muestra: caracteres por página, tablas detectadas (`find_tables()`), líneas que
parecen títulos de artículo, capítulo o disposición (expresiones regulares), líneas que se
repiten en muchas páginas (posibles encabezados) y caracteres de control. Los casos raros
(modificaciones, rúbrica, calendario) los he revisado imprimiendo el texto de páginas
concretas.

### Conclusiones (requisitos para el script de extracción)
1. **Limpieza de encabezados**: eliminar las líneas que se repiten en muchas páginas
   (membretes de la ESI y del Vicerrectorado) y la cabecera del BOUCA de la p. 1. No basta
   con buscar "BOUCA", porque también aparece en citas.
2. **Limpieza de caracteres**: quitar los caracteres de control (`\x03`), normalizar los
   espacios no separables (`\xa0`) y quitar los números de nota al pie pegados al texto.
3. **Rango útil por documento**: descartar portadas, preámbulos, historiales, índices,
   anexos y contenido ajeno. Como cada documento es distinto, indicar en `sources.csv` las
   páginas útiles de cada uno (`pagina_inicio`, `pagina_fin`).
4. **Unir antes de trocear**: concatenar el texto de todas las páginas útiles y después
   unir las líneas de cada párrafo. Si se trocea página a página, se cortan artículos.
5. **Trocear por artículo con un patrón flexible**: `^(Artículo|Art\.)\s*\d+` cubre todas
   las variantes vistas. Guardar como metadatos: documento, título/capítulo/bloque, número
   de artículo y página. Subdividir los artículos muy largos por apartados.
6. **Casos especiales fuera del pipeline general**: el calendario y la rúbrica necesitan
   un tratamiento propio, no el troceado por artículos.

### Dudas abiertas
- **Modificaciones**: ¿indexo el original y la modificación por separado (y añado un aviso
  de "modificado por..."), o construyo un texto consolidado sustituyendo los artículos
  cambiados? Lo segundo da respuestas más fiables, pero es más trabajo, sobre todo con la
  renumeración de 2014.
- **Calendario**: ¿lo transcribo a mano a un archivo de texto con las fechas clave, o lo
  dejo fuera de esta primera versión?
- **Rúbrica**: ¿la convierto a texto a mano, con un script a partir de `find_tables()`, o
  la dejo para más adelante?
- **Preámbulos**: no responden dudas prácticas, pero sí preguntas tipo "¿por qué existe
  esta norma?". ¿Los incluyo o no?

### Decisiones
- **Modificaciones → texto consolidado propio.** Aplicaré los cambios de 2014 y 2015 sobre
  los reglamentos de 2012 para obtener la redacción vigente de cada artículo, en lugar de
  indexar originales y modificaciones por separado. **Motivo:** quiero asegurar respuestas
  de calidad aunque cueste más trabajo. Si indexo por separado, el RAG puede recuperar la
  redacción antigua de un artículo ya modificado y responder mal, y habría dos "artículo 9"
  con contenido distinto por la renumeración de 2014.
- **Calendario, rúbrica y preámbulos → fuera de la primera versión.** Los añadiré más
  adelante, cuando tenga una base del RAG funcionando y pueda medir si mejoran o empeoran
  las respuestas con el conjunto de evaluación. Quedan como mejoras futuras:
  - Calendario: transcribir a mano las fechas clave a un archivo de texto.
  - Rúbrica: convertir la tabla en frases con sentido (a mano o a partir de `find_tables()`).
  - Preámbulos: experimento de "¿mejora o empeora el RAG al incluirlos?".

---

## 2026-11-24 · Sesión 3: extracción y limpieza del texto (paso 2)

### Qué he hecho
- Analizo al detalle qué cambia cada modificación:
  - **2014 (TFG), 4 cambios**: añade un Capítulo II con los artículos 9-13 (dobles
    títulos), agrupa los artículos 1-8 en un "Capítulo primero", renumera los antiguos
    9 y 10 como 14 y 15 (Capítulo III) y añade una frase a los artículos 2 y 6.
  - **2015 (prácticas), 16 cambios**: 4 artículos completos (37, 38, 51 y 54) y el resto
    son apartados sueltos ("el apartado 2 del artículo 13", "la letra b del apartado 3
    del artículo 14"...). El texto nuevo va entre `<<` y `>>`.
- Añado a `data/sources.csv` las columnas `pagina_inicio` y `pagina_fin` con el rango
  útil de cada documento (vacías en el calendario y la rúbrica, que quedan fuera).
- Creo `src/ingest.py`, que extrae el texto del rango útil de cada PDF, lo limpia y lo
  guarda en `data/processed/<id>.txt` (ignorado en Git: es texto de los PDFs y se
  regenera con el script).

### Decisiones
- **Consolidación con un archivo de parches** (`data/parches.json`, todavía por hacer).
  Como casi todos los cambios afectan a trozos de artículo, no basta con sustituir
  artículos enteros. Cada cambio será una operación (`reemplazar_texto`,
  `reemplazar_articulo`, `añadir_articulo`, `renumerar`) que un script aplica sobre los
  artículos originales. Es reproducible, verificable (si el texto antiguo no aparece, el
  script falla) y trazable (cada artículo sabe qué modificación lo cambió).
- **Reglas de limpieza generales, no por documento.** Ninguna regla menciona un archivo
  concreto, para que funcionen con documentos nuevos sin añadir casos especiales.
- **Los tamaños de letra se comparan con el cuerpo de cada documento**, no con un valor
  fijo: el cuerpo mide 12, 12, 11, 10 y 12 pt según el PDF. Con un umbral fijo de 9 pt,
  un documento futuro con cuerpo de 9 pt se borraría entero.

### Cómo funciona `src/ingest.py`
1. `tamano_cuerpo()`: el tamaño de letra con más caracteres en el rango útil.
2. `lineas_pagina()`: lee cada página con `get_text("dict")` (bloques → líneas → spans,
   cada span con su tamaño y cada línea con su posición) y quita:
   - el texto más de 2 pt menor que el cuerpo, esté donde esté (llamadas de nota,
     membretes y notas en letra muy pequeña);
   - las líneas algo menores que el cuerpo que están **debajo** de la última línea del
     cuerpo de la página (notas al pie).
3. `detectar_encabezados()`: líneas que aparecen en al menos la mitad de las páginas
   (membretes), salvo marcas de apartado como `a)` o `1.`.
4. `limpiar_linea()`: quita caracteres de control (`\x03`), cambia `\xa0` por espacio y
   deja un solo espacio entre palabras.
5. `extraer_texto()`: aplica todo lo anterior, quita las líneas `pág. N` y une las
   páginas sin crear párrafos falsos en los saltos de página.

### Problemas y soluciones
- **`a)` y `b)` detectados como membretes.** En el reglamento de prácticas aparecen en 11
  de 22 páginas, así que la regla de líneas repetidas los habría borrado todos. Solución:
  excluir de esa regla las líneas que son solo una marca de apartado.
- **Membrete en mitad de una frase.** En la modificación de 2014, el membrete del
  Vicerrectorado aparece justo en un salto de página que parte la cláusula SEGUNDO. Al
  quitarlo y no dejar líneas en blanco en los bordes de página, la frase queda seguida.
- **La nota al pie 2 de la ESI no se eliminaba.** Está a 10 pt con un cuerpo de 11 pt, y
  la regla de "más de 2 pt menor" no la cogía. Bajar el margen a 1 pt era arriesgado: en
  la p. 1 del reglamento marco hay contenido real a 11 pt con cuerpo de 12 pt. Solución:
  combinar **tamaño y posición**: el texto algo menor solo se quita si está debajo del
  cuerpo de la página, que es donde van las notas al pie.
- **Aviso de Git "LF will be replaced by CRLF".** No es un error: Git para Windows
  convierte los finales de línea. En GitHub los archivos quedan con LF.

### Validación
Comparo palabra por palabra el texto de los PDFs (mismo rango) con `data/processed/`:

| Documento | Palabras PDF → procesado | Eliminado | Añadido |
|---|---|---|---|
| tfg_uca_2012 | 3.748 → 3.748 | nada (solo `\x03`) | nada |
| tfg_uca_2014 | 1.130 → 1.052 | 3 membretes | nada |
| tfgm_esi | 4.353 → 3.955 | 11 membretes, 2 notas al pie y sus 2 llamadas | nada |
| practicas_uca_2012 | 9.855 → 9.855 | nada | nada |
| practicas_uca_2015 | 1.678 → 1.678 | nada | nada |

También compruebo que están todos los artículos en orden y sin repetir (10, 25 y 56),
las cláusulas PRIMERO-QUINTO y los artículos 9-13 de 2014, y los 16 cambios de 2015 con
sus `<<` `>>` emparejados.

**Limitación:** las reglas están probadas con estos 5 documentos. Se basan en supuestos
(el cuerpo es el tamaño más frecuente, lo que hay debajo del cuerpo son notas al pie, el
PDF tiene texto real a una columna...) que un documento nuevo podría no cumplir. Cada vez
que añada uno hay que explorarlo, fijar su rango, extraerlo y **validar** que solo se
elimina ruido.

### Script de validación: `scripts/validar_extraccion.py`
Convierto esa comprobación en un script del proyecto, para repetirla cada vez que cambie
las reglas de limpieza o añada un documento. Se ejecuta después de `ingest.py`:

```
python src/ingest.py
python scripts/validar_extraccion.py
```

Para cada documento compara palabra por palabra el texto del PDF con su `.txt` procesado
(con `difflib.SequenceMatcher`, que describe las diferencias como operaciones `equal`,
`delete`, `insert` y `replace`) y comprueba:

| # | Comprobación | Cómo |
|---|---|---|
| 1 | No se ha **añadido** texto | Automática: falla si hay algo. Única excepción: una llamada de nota pegada ("momento.2" → "momento.") |
| 2 | Qué se ha **quitado** | Revisión manual: lo muestra agrupado (ignorando números, para que el membrete de cada página cuente como uno) |
| 3 | No quedan caracteres de control ni `\xa0` | Automática |
| 4 | Los artículos son **consecutivos** y no se repiten | Automática (no exige empezar en 1: la modificación de 2014 tiene los artículos 9-13) |

Si falla alguna comprobación automática, termina con **código de salida 1** (convención
para que otras herramientas, como GitHub Actions en el futuro, sepan que algo ha ido mal).

**Prueba de que detecta errores:** estropeé a propósito una copia del reglamento marco
(una frase inventada con un `\x03` y el "Art. 5.º" cambiado por "Art. 7.º"). El script
detectó las tres cosas: texto añadido, carácter de control y artículos no consecutivos
`[1, 2, 3, 4, 7, 6, ...]`, y terminó con código 1. Un validador que siempre dice ✓ no
sirve de nada, así que hay que probar también que falla cuando debe.

**Principio importante: la referencia tiene que ser independiente.** El validador usa
`get_text()` en bruto como "original", y no `extraer_texto()` de `ingest.py`. Si usara mi
propia función, un error en ella (por ejemplo, que se coma el artículo 5) estaría en los
dos lados de la comparación, los dos textos coincidirían y el validador diría ✓. Sería como
corregir mi propio examen con mis propias respuestas. Con el texto en bruto, ningún error
de mis reglas puede colarse en la referencia.
- Lo único que comparten es la normalización de `palabras()` (quitar caracteres de control
  y `\xa0`), para no llenar el informe de avisos por cosas que se quitan a propósito. Por
  eso esa parte se comprueba aparte (comprobación 3).
- La misma idea se aplicará en el paso 4: las preguntas de evaluación las escribiré a mano
  leyendo la normativa, no generadas por el propio RAG, porque si no se evaluaría a sí mismo.

Resultado actual: **5/5 documentos superan las comprobaciones automáticas**, y lo quitado
es solo membretes, notas al pie y sus llamadas.

### Pendiente
- Dividir el texto de cada reglamento en artículos.
- Escribir `data/parches.json` y aplicar las modificaciones para obtener el texto
  consolidado.
- Unir las líneas de cada párrafo (ahora cada línea del PDF es una línea del texto).
- Descartar los restos de preámbulo o justificación al principio de tfg_uca_2012,
  tfg_uca_2014 y practicas_uca_2015.

---

## 2026-11-25 · Sesión 4: división de los reglamentos en artículos (paso 2)

### Qué he hecho
- Añado a `data/sources.csv` la columna `tipo` (`reglamento`, `modificacion`, `otro`). Solo
  los 3 reglamentos se dividen en artículos; las modificaciones se pasarán a parches.
- Creo `src/articulos.py`, que divide el texto de cada reglamento en **unidades**
  (artículos y disposiciones) y las guarda en `data/processed/articulos/<id>.json`:

```json
{
  "id": "tfgm_esi_art_12",
  "documento": "tfgm_esi",
  "tipo": "articulo",
  "numero": 12,
  "titulo": "Validez de la asignación de los TFG/M",
  "seccion": "LA PROPUESTA Y ASIGNACIÓN DE LOS TFG/M",
  "encabezado": "Artículo 12. Validez de la asignación de los TFG/M.",
  "texto": "a) La asignación tendrá una validez de 2 años naturales...\nb) El estudiante que haya suspendido..."
}
```

### Decisiones
- **Expresiones regularescomo base**, con la opción de usar la letra negrita del PDF como
  plan de reserva si algún documento falla. No ha hecho falta.
- **Las disposiciones también son unidades** (`tipo: "disposicion"`, `numero: null`):
  tienen contenido útil (entrada en vigor, igualdad de género, régimen transitorio).
- **`seccion`** guarda el nivel superior: el bloque en la ESI ("EL EXAMEN DE TFG/M") o
  `TÍTULO > CAPÍTULO` en prácticas. Vacía en el reglamento marco (no tiene) y en las
  disposiciones (van fuera de los capítulos).
- **Se descarta lo anterior al primer artículo** (restos del preámbulo).
- **Se unen las líneas de cada párrafo**, pero cada apartado (`1.`, `a)`, `iii.`) empieza
  en su propia línea. Así el texto se lee bien y los parches podrán localizar apartados.
- **No se guarda la página**: al unir páginas se perdió y para citar basta el artículo.

### Cómo distingue un título de una mención
Un título de artículo tiene que:
1. empezar por `Artículo` o `Art.` con **mayúscula**;
2. tener detrás del número un título que **empiece por mayúscula** (`artículo 12.2 del
   Real Decreto` no vale);
3. llevar **el número que toca** (el siguiente al último). Si no, se trata como texto y
   se muestra un aviso.

### Problemas y soluciones
- **"DISPOSICIONES GENERALES" tomado por una disposición.** Es el nombre del Título Primero
  del reglamento de prácticas. Solución: una disposición tiene que decir de qué tipo es
  (adicional, transitoria, derogatoria o final).
- **Encabezados de sección no detectados** ("CAPÍTULO II." y "LA TUTELA DE LOS TFG/M.") y
  metidos en el texto del artículo anterior, porque no iban después de una línea vacía.
  Solución: `TÍTULO`/`CAPÍTULO` siempre son sección, y una línea en mayúsculas de al menos
  dos palabras también si está pegada a una línea vacía. Así "TFG/M." (final de un
  párrafo partido) sigue sin contar como sección.
- **Las disposiciones heredaban el último capítulo** ("CAPÍTULO VI. PREMIOS"). Solución:
  al empezar una disposición se vacía la sección.
- **Título partido en dos líneas** (Art. 9.º del reglamento marco). Solución: si el título
  no termina en `.`, `.-` o `:`, sigue en la línea siguiente.

### Validación
El propio script comprueba, para cada reglamento, que **cada palabra del texto acaba en
un único sitio** (encabezado, texto, sección o descartado), que los artículos son
consecutivos desde 1 y que ninguna unidad queda vacía. Si algo falla, termina con código 1.

| Reglamento | Artículos | Disposiciones | Secciones | Descartado |
|---|---|---|---|---|
| tfg_uca_2012 | 10 | 2 | — | 477 palabras (preámbulo) |
| tfgm_esi | 25 | 2 | 8 bloques | 110 palabras (preámbulo) |
| practicas_uca_2012 | 56 | 8 | 4 títulos, 17 capítulos | 0 |

Revisión manual: comprobé que cada artículo cae en su sección (por ejemplo, ESI 13-15 en
"LA TUTELA DE LOS TFG/M"; prácticas 5-6 en "CAPÍTULO II. MODALIDADES"), que no queda
ningún "CAPÍTULO" ni encabezado en mayúsculas dentro de los textos, y leí completos los
artículos 9 del marco, 12 de la ESI y 5 y 14 de prácticas.

### Decisiones sobre las modificaciones y las versiones
- **Solo se dividen en artículos los 3 reglamentos.** Las modificaciones no son normas
  completas sino instrucciones de cambio; se convertirán en parches. El calendario y la
  rúbrica siguen fuera de la primera versión.
- **Las modificaciones se guardan en `data/parches.json`**, una entrada por cambio, con:
  `fuente` (qué modificación), `cambio` ("Dos", "PRIMERO"...), `reglamento`, `articulo`,
  `operacion` (`reemplazar_texto`, `reemplazar_articulo`, `añadir_articulo`, `renumerar`),
  `texto_antiguo` y `texto_nuevo`. Si un `texto_antiguo` no aparece exactamente en el
  artículo, el script falla: no se puede aplicar un cambio en el sitio equivocado sin
  enterarse.
- **Al RAG solo va la versión vigente** (consolidada). Si indexara también la antigua, el
  buscador podría recuperar la redacción de 2012 de un artículo ya modificado y el LLM
  respondería con una norma que ya no se aplica. El usuario es un estudiante que quiere
  saber qué tiene que hacer hoy.
- **No duplico los textos originales en el consolidado.** Al principio pensé en guardar un
  campo `texto_original` en cada artículo modificado, pero los originales ya están en
  `data/processed/articulos/*.json` y se pueden regenerar desde los PDFs. Copiarlos sería
  duplicar información, y si un día cambiara una copia y no la otra dejarían de
  coincidir. Cada versión se obtiene de las demás:

  ```
  data/processed/articulos/*.json     → versión original (2012), tal como sale del PDF
  data/parches.json                   → los cambios (2014 y 2015)
  data/processed/consolidado/*.json   → versión vigente = original + parches  → al RAG
  ```

- **Cada artículo consolidado guarda `modificado_por`** (lista de modificaciones que lo han
  cambiado). Sí aporta información nueva: la respuesta puede citar "art. 13, en la
  redacción de la modificación de 2015", y indica dónde mirar la versión original.
- **Mejora futura:** responder preguntas sobre normas antiguas indexando también las
  versiones anteriores con un metadato `vigente: false` y filtrando por defecto solo las
  vigentes.

### Pendiente
- Escribir `data/parches.json` con los cambios de 2014 y 2015 y aplicarlos para obtener
  el texto consolidado en `data/processed/consolidado/`.

---

## 2026-11-25 · Sesión 5: borrador de los parches (paso 2)

### Qué he hecho
- Creo `scripts/borrador_parches.py`, que genera un **borrador** de los parches en
  `data/processed/parches_borrador.json` (ignorado en Git). No es el archivo definitivo:
  hay que revisarlo a mano y guardar el resultado como `data/parches.json`.
- **Modificación de 2015 (automático):** todos sus cambios siguen el esquema "el apartado
  X del artículo N queda redactado como sigue: <<texto nuevo>>". El script extrae el
  artículo y cada bloque `<<...>>`, busca en el artículo original el apartado con la misma
  marca (`2.`, `b)`, `iii.`) y propone ese texto como `texto_antiguo`.
- **Modificación de 2014 (a mano, en `borrador_2014()`):** sus cambios son de tipos
  distintos, así que están escritos uno a uno. Los textos largos (artículos 9-13 nuevos)
  sí se extraen del documento.

Operaciones, que se aplicarán en el orden de la lista:

| Operación | Qué hace | Usada en |
|---|---|---|
| `reemplazar_texto` | Cambia `texto_antiguo` por `texto_nuevo` dentro de un artículo | 2015 (apartados), 2014 TERCERO y CUARTO |
| `reemplazar_articulo` | Sustituye título y texto de un artículo entero | 2015: arts. 37, 38, 51 y 54 |
| `renumerar` | Cambia el número de un artículo | 2014: 9 → 14 y 10 → 15 (antes de añadir los nuevos) |
| `añadir_articulo` | Inserta un artículo nuevo | 2014: arts. 9-13 (dobles títulos) |
| `asignar_seccion` | Pone el capítulo de una lista de artículos | 2014: capítulos primero, II y III |

### Resultado del borrador
36 parches (12 de 2014 y 24 de 2015). Todos los `texto_antiguo` aparecen **exactamente
una vez** en su artículo. 9 parches tienen avisos para revisar:
- **2014, art. 13 sin título:** en la modificación empieza directamente con el texto.
- **2014, TERCERO ("párrafo cuarto del artículo 6.º"):** en el PDF el 4.º párrafo es
  "Además, los alumnos podrán proponer...", pero en nuestro texto aparece unido al 3.º
  porque empezaba en una página nueva (ver limitación abajo). Además, la frase añadida
  tiene una errata del original ("las comisión").
- **2014, CUARTO:** no dice dónde se añade la frase; se ha puesto antes del punto final.
- **2015, Uno:** el apartado 1 del art. 6 ocupa 2 párrafos en el original.
- **2015, Tres y Cuatro:** marcas compuestas (`3.b)`, `d). iii`) reescritas al formato del
  original (`b)`, `iii.`).
- **2015, Cuatro (iii):** el texto nuevo es igual al antiguo.
- **2015, Cuatro (último párrafo):** el bloque no tiene marca; se supone que es el último
  párrafo del art. 15, como dice el enunciado.
- **2015, Trece:** el enunciado dice "los apartados 3" pero trae los bloques 3 y 4, y el 4
  sí cambia (9 palabras).

### Limitación descubierta
`ingest.py` quita las líneas vacías del principio y el final de cada página para no partir
frases en los saltos de página. El efecto secundario es que, si un párrafo termina justo al
final de una página y el siguiente empieza en la página nueva, **los dos quedan unidos**.
No se pierde texto, pero contar párrafos ("párrafo cuarto") puede no coincidir con el PDF.

### Revisión del borrador
Reviso los 9 avisos mirando el texto real y las diferencias palabra a palabra entre el
texto antiguo y el nuevo:

| # | Aviso | Decisión |
|---|---|---|
| 1 | 2014, art. 13 sin título | **Sin título.** Inventarlo sería añadir texto que no está en la norma; el RAG lo encontrará por su contenido |
| 2 | 2014 TERCERO, "párrafo cuarto" del art. 6 | **Correcto.** Comprobado en el PDF: la p. 7 empieza con el 4.º párrafo ("Además, los alumnos podrán proponer..."), que termina en "tutor del trabajo" |
| 3 | 2014 TERCERO, errata "las comisión" | **Se copia tal cual.** Es el texto oficial: un sistema que cita normativa no debe corregirla por su cuenta |
| 4 | 2014 CUARTO, dónde va la frase | **Antes del punto final.** Empieza por coma, igual que la del TERCERO |
| 5 | 2015 Uno, apartado en 2 párrafos | **Correcto.** Solo cambia el Real Decreto (1707/2011 → 592/2014); la 2.ª frase es igual |
| 6 | 2015 Tres, marca `3.b)` | **Correcto.** Encuentra la letra b del apartado 3 (no la del 2) |
| 7 | 2015 Cuatro, epígrafe iii igual al antiguo | **Se elimina el parche.** No cambia nada; el art. 15 queda igualmente modificado por el parche del último párrafo |
| 8 | 2015 Cuatro, último párrafo sin marca | **Correcto.** Mismo párrafo; solo cambia "Director General" → "Vicerrector" |
| 9 | 2015 Trece, enunciado "apartados 3" con bloques 3 y 4 | **Se aplican los dos.** Hacen el mismo cambio y el plural "Los apartados" indica una errata del enunciado |

Resultado: **`data/parches.json` con 35 parches** (36 del borrador menos el del punto 7),
todos con `"revisado": true`. Quito los campos auxiliares del borrador (`revisar`,
`palabras_que_cambian`) y añado un campo `nota` en los parches con una decisión
(puntos 1, 2-3, 4 y 9), para que el motivo quede junto al dato. Todos los
`texto_antiguo` siguen apareciendo exactamente una vez en su artículo.

| Modificación | Operación | Parches |
|---|---|---|
| 2014 | `renumerar` | 2 |
| 2014 | `añadir_articulo` | 5 |
| 2014 | `asignar_seccion` | 3 |
| 2014 | `reemplazar_texto` | 2 |
| 2015 | `reemplazar_texto` | 19 |
| 2015 | `reemplazar_articulo` | 4 |

**Patrón observado:** casi todos los cambios de 2015 sustituyen al "Director General de
Universidad y Empresa" por el "Vicerrector competente en la materia" y actualizan el Real
Decreto 1707/2011 por el 592/2014. La modificación adaptó el reglamento a un cambio de
organigrama y a la nueva ley. Sin consolidar, el RAG mandaría al estudiante a un cargo
que ya no existe.

**`data/parches.json` es ahora la fuente de verdad.** El borrador solo sirvió para
prepararlo; si se vuelve a generar, no toca `data/parches.json`.

### Pendiente
- Crear `src/consolidar.py`, que aplique los parches y genere `data/processed/consolidado/`.

---

## 2026-11-25 · Sesión 6: consolidación de las modificaciones (cierre del paso 2)

### Qué he hecho
Creo `src/consolidar.py`, que lee los artículos originales (`data/processed/articulos/`) y
los parches revisados (`data/parches.json`), los aplica en orden y guarda la **versión
vigente** en `data/processed/consolidado/<id>.json`. Esta es la versión que irá al RAG.

Cada unidad consolidada tiene: `id`, `documento`, `tipo`, `numero`, `titulo`, `seccion`,
`texto` y `modificado_por`. Quito el campo `encabezado` (el texto del título tal como sale
del PDF): dejaría de cuadrar al renumerar ("Art. 9.º" en un artículo que ahora es el 14).

### Decisiones
- **El script es estricto y se detiene ante cualquier problema** (código de salida 1): un
  parche sin revisar, un texto antiguo que no aparece exactamente una vez, un artículo que
  no existe, añadir un artículo con un número ya ocupado o artículos que al final no van
  del 1 al N sin huecos. Prefiero que falle a que aplique un cambio mal sin avisar.
- **`asignar_seccion` no marca el artículo como modificado**: cambiar el capítulo no cambia
  el contenido. Renumerar sí lo marca (el artículo 14 de hoy era el 9 en 2012).
- **El reglamento de la ESI pasa sin cambios** (no tiene parches), para que todo el corpus
  salga en el mismo formato y desde la misma carpeta.

### Resultado

| Reglamento | Parches | Resultado | Artículos modificados |
|---|---|---|---|
| tfg_uca_2012 | 12 | 15 artículos (antes 10), 2 disposiciones, en 3 capítulos | 2, 6, 9-15 |
| tfgm_esi | 0 | 25 artículos, 2 disposiciones | — |
| practicas_uca_2012 | 23 | 56 artículos, 8 disposiciones | 6, 13, 14, 15, 17, 22, 23, 24, 26, 31, 37, 38, 39, 51, 52, 54 |

### Validación
- Los 83 artículos y disposiciones **sin parches son idénticos** a los originales.
- **Todos los textos nuevos de 2015** están en el consolidado.
- **No queda ninguna mención** a "Director General" ni al Real Decreto 1707/2011 en el
  reglamento de prácticas: la consolidación ha llegado a todos los sitios donde debía.
- **Prueba de que rechaza errores:** le pasé parches estropeados a propósito y falló en
  los 5 casos con un mensaje claro: parche sin revisar, texto antiguo inexistente, añadir
  el artículo 9 sin renumerar antes, artículo inexistente y el mismo parche aplicado dos
  veces (la segunda vez el texto antiguo ya no aparece).

### Pipeline completo del paso 2

```
python src/ingest.py                  # PDF -> texto limpio
python scripts/validar_extraccion.py  # comprobar que no se pierde ni se inventa texto
python src/articulos.py               # texto -> artículos (versión original)
python src/consolidar.py              # artículos + parches -> versión vigente
```

### Pendiente
- Paso 3 (troceado): decidir si cada artículo es un chunk o si los artículos largos se
  subdividen, y qué metadatos lleva cada chunk.

## 2026-11-25 · Sesión 7: troceado en chunks (paso 3)

### Qué he aprendido antes de empezar
- Un **embedding** es un vector de números que representa el significado de un texto. El
  modelo está entrenado para que textos con significado parecido queden cerca (similitud
  coseno), aunque no compartan palabras: "¿me pagan por las prácticas?" encuentra "ayuda
  al estudio". Falla con lo exacto (números de artículo, cifras, siglas): por eso en el
  paso 8 probaré la búsqueda híbrida.
- El modelo de embeddings no es el LLM: es pequeño, se ejecuta en local y solo convierte
  texto en vectores. Muchos tienen un límite de ~512 tokens (~350-400 palabras en español).
- **Cada chunk se resume en un solo punto.** Si es muy grande, su vector es un "promedio"
  de varios temas y no se parece especialmente a ninguna pregunta (y lo que pase del
  límite se corta sin avisar). Si es muy pequeño, pierde el contexto.
- La mayoría de los fallos de un RAG son de **recuperación**: si el artículo correcto no
  llega al LLM, da igual lo bueno que sea el LLM.

### Datos del corpus consolidado
108 unidades, 16.600 palabras. Mediana 124 palabras por unidad, el 90 % ≤ 308, máximo 675
(art. 21 de la ESI). 11 unidades pasan de 300 palabras.

### Decisiones
- **Artículo entero salvo los largos, que se dividen por apartados.** Las
  alternativas eran A (un artículo = un chunk) y C (trozos de tamaño fijo con
  solapamiento, que ignora la estructura y corta artículos por la mitad). B respeta la
  estructura de la norma y la cita sigue siendo precisa ("art. 22, apartados 7-14"). A no
  se descarta: será la línea base del experimento de troceado del paso 8.
- **Máximo de 300 palabras por chunk** (~400-450 tokens), para que quepa en modelos con
  límite de 512.
- **Se divide por los apartados de primer nivel**: el tipo de marca con que empieza el
  artículo ("1." o "a)"). Los subapartados y los párrafos sin marca se quedan con su
  apartado: nunca se parte un apartado por la mitad.
- **Reparto equilibrado:** se calcula cuántos trozos hacen falta y se reparten los
  apartados a partes parecidas, para no dejar un último trozo diminuto.
- **La frase introductoria se repite en cada trozo** ("La entidad colaboradora está
  obligada a:"), porque sin ella "7. Comunicar las faltas de asistencia…" no se entiende.
- **Encabezado de contexto** (*contextual chunk header*): el texto que se convierte en
  embedding lleva delante "documento > sección > Art. N. Título (apartados x-y)". Se
  guardan los dos textos: `texto` (para mostrar y citar) y `texto_embedding`.
- **Metadatos de cada chunk:** id, documento, titulo_documento y url (de `sources.csv`),
  tipo, numero, titulo, seccion, modificado_por, apartados, parte y partes.

### Resultado

| Reglamento | Unidades | Chunks | Unidades divididas |
|---|---|---|---|
| tfg_uca_2012 | 17 | 22 | 5 (arts. 2, 4, 5, 6, 7) |
| tfgm_esi | 27 | 32 | 2 (arts. 21 y 22) |
| practicas_uca_2012 | 64 | 68 | 4 (arts. 8, 14, 22, 48) |

122 chunks: mínimo 16 palabras, mediana 136, máximo 315. Dos chunks pasan un poco de 300
(el art. 21 de la ESI, apartados b) y d)) porque son un solo apartado con 5 y 4
subapartados; el script avisa, pero no los parte.

### Validación
- El script comprueba que, quitando las introducciones repetidas, los trozos de cada
  artículo **reproducen su texto exacto**, que cada trozo empieza por la introducción y que
  no hay ids repetidos. Si algo falla, se detiene con código de salida 1.
- **Prueba negativa:** cambiar una palabra de un trozo, borrar un trozo y quitar la
  introducción de un trozo: los tres casos se detectan.

### Limitaciones
- El reparto es "voraz" (va llenando trozos en orden), así que a veces queda un trozo
  pequeño: el art. 22 de la ESI sale en 222 + 293 + 54 palabras. Como los apartados
  pequeños tratan un tema propio, no lo considero un problema.

### Apuntes: para qué sirven los metadatos de cada chunk
El embedding sirve para **encontrar** el chunk; los metadatos, para todo lo que pasa
después:
1. **Citar sin que el LLM se lo invente.** Cada chunk llega al prompt etiquetado con su
   documento, artículo y apartados, y la interfaz puede enlazar al PDF oficial (`url`).
2. **Evaluar automáticamente.** El Recall@k compara el `documento` y el `numero` de los
   chunks recuperados con las fuentes de cada pregunta; cualquier trozo de un artículo
   dividido cuenta como acierto.
3. **Filtrar la búsqueda** (por ejemplo, solo el reglamento de prácticas), para que no se
   cuele un artículo del reglamento equivocado.
4. **Reconstruir el artículo completo** con `parte`/`partes`: si se recupera el trozo 2,
   se le puede pasar también el 1 al LLM (*parent document retrieval*) o agrupar los dos
   como una sola fuente.
5. **Transparencia** con `modificado_por`: "redacción dada por la modificación de 2015".
6. **Depurar**: cuando una pregunta falle, se ve al instante qué artículo trajo en su lugar.

### Pendiente
- Paso 4: escribir el conjunto de evaluación (40-60 preguntas con su artículo correcto)
  antes de indexar, para poder medir cada decisión.

## 2026-11-26 · Sesión 8: conjunto de evaluación (paso 4)

### Qué es y para qué sirve
Una lista de preguntas con su respuesta de referencia y los artículos donde está la
respuesta. No la usa el RAG al responder: es una **muestra** para medirlo, como un
examen. Si acierta el 85 % de estas preguntas, estimo que acertará más o menos el 85 % de
las reales, siempre que la muestra se parezca a cómo preguntan los alumnos. Va antes de
indexar para no escribir, sin querer, preguntas "fáciles" para el sistema.

Métricas que permitirá calcular: Recall@k y MRR (paso 6), corrección de la respuesta y
abstención ante preguntas sin respuesta (paso 7).

### Apuntes: las preguntas no tienen que coincidir con las de los usuarios
El RAG nunca consulta `questions.json`: compara la pregunta del usuario con los chunks y
por significado, no palabra por palabra. Un sistema que buscase la pregunta más parecida
en una lista fija sería un chatbot de preguntas frecuentes (FAQ), no un RAG. Las preguntas
de evaluación son una **muestra**, como un examen: lo que importa es que su variedad
(temas, formas de preguntar, dificultad) se parezca a la de los usuarios reales. Riesgo:
"aprenderse el examen" si se ajusta el sistema hasta acertar estas preguntas concretas;
por eso habrá 10 preguntas nuevas al final. Cuando la demo esté publicada, las preguntas
reales de los usuarios servirán para ampliar el conjunto.

### Decisiones
- **Formato** (`eval/questions.json`): id, pregunta, respuesta, fuentes (ids de las
  unidades del consolidado, sin `_p1`/`_p2`, para que cualquier trozo de un artículo
  dividido cuente como acierto) y tipo.
- **Seis tipos** para cubrir los puntos fuertes y débiles de un RAG: `directa`
  (vocabulario del reglamento), `parafrase` (como lo diría un alumno), `cifra` (horas,
  plazos, porcentajes: la debilidad de los embeddings), `multi` (respuesta en varios
  artículos), `ambigua` (el marco UCA y el reglamento de la ESI dicen cosas distintas) y
  `sin_respuesta` (para comprobar que el LLM no se inventa nada).
- **Riesgo de sesgo:** quien escribe las preguntas ha leído los artículos, así que pueden
  acercarse a su vocabulario. Para compensarlo: revisarlas una a una contra el artículo,
  incluir dudas reales de alumnos y, al final del proyecto, escribir 10 preguntas nuevas
  como comprobación limpia.
- **Script de validación** (`scripts/validar_preguntas.py`): comprueba campos, tipos,
  ids y preguntas repetidas, que cada fuente exista en el consolidado, que las
  `sin_respuesta` (y solo ellas) vayan sin fuentes y que las `multi` tengan al menos 2.
  Además mide el **solapamiento de vocabulario** entre cada pregunta y sus fuentes y
  avisa si una pregunta que no es `directa` repite demasiadas palabras del artículo.

### Resultado

| Tipo | Preguntas | Solapamiento medio |
|---|---|---|
| directa | 15 | 0,65 |
| parafrase | 13 | 0,39 |
| cifra | 11 | 0,45 |
| multi | 7 | 0,43 |
| ambigua | 11 | 0,68 |
| sin_respuesta | 5 | — |

62 preguntas: 41 citan prácticas, 34 la ESI y 23 el marco. Cubren 54 de los 108
artículos y disposiciones. El solapamiento confirma que las de tipo `parafrase` se
alejan del vocabulario del reglamento más que las `directa`.

Ejemplos de preguntas `ambigua` interesantes: la validez de la asignación del TFG (el
marco dice un curso, la ESI dos años) y los requisitos para defender (básicas y
obligatorias en el marco, todas las materias en la ESI).

### Limitación del solapamiento
Es una medida aproximada: palabras como "TFG", "tutor" o "prácticas" salen en casi
todos los artículos y suben el porcentaje en preguntas cortas, aunque estén bien
formuladas (por eso salen avisos que, revisados, no son problemas de redacción. Una pregunta tan natural como "¿Cuántos tutores de TFG tengo?" da un 100 %).

### Revisión de las respuestas de referencia
Las fuentes y respuestas son la "solución" del examen: si están mal, la evaluación
castiga al sistema cuando acierta. `scripts/revisar_preguntas.py` muestra cada pregunta
con el texto completo de sus fuentes para revisarlas. Correcciones:
- **El error más frecuente era una fuente que faltaba**, no una respuesta equivocada. Se
  han añadido fuentes en 14 preguntas. Por ejemplo, "¿quién me da un papel que demuestre
  lo que he hecho?" no citaba el art. 23.4 de prácticas (la UCA debe expedir la
  acreditación), y la pregunta sobre dobles grados hablaba del tribunal de cuatro
  miembros sin citar los artículos que lo dicen.
- "¿Cuántos créditos vale el TFG?" pasa de `sin_respuesta` a `cifra`: los reglamentos no
  dan una cifra, pero sí dicen de dónde sale (la memoria del título). Marcarla sin fuentes
  habría castigado al buscador por encontrar justo lo que debe.
- En "¿cuánto dinero puedo ganar?" la respuesta ahora menciona que las cantidades las
  aprueba el Vicerrector mediante Instrucción, sin interpretar más de lo que dice el texto.

Es probable que aún falte alguna fuente. En el paso 6, cada vez que el buscador falle se
revisará si el artículo que trajo también respondía; así la revisión se guía por los
errores reales en lugar de releer todo.

### Validación
Prueba negativa: una fuente inexistente, una `sin_respuesta` con fuentes, un id
repetido, un campo que falta, un tipo desconocido y una `multi` con una sola fuente. Los
seis casos se detectan.

### Pendiente
- Paso 5: indexación (embeddings + Chroma).

## 2026-11-26 · Sesión 9: indexación (paso 5)

### Apuntes: qué es la indexación
Convertir los 122 chunks en vectores **una sola vez** y guardarlos en una base de datos
preparada para buscar vectores parecidos:

```
chunks.json (texto_embedding) → modelo de embeddings → 122 vectores → Chroma (en disco)
```

En cada pregunta solo hay que calcular un embedding (el de la pregunta) y pedirle a
Chroma los k vectores más cercanos (paso 6). Es el paso en el que el proyecto deja de
preparar texto y se convierte en un buscador semántico.

### Apuntes: qué es un embedding y qué hace el modelo
*To embed* es "incrustar": un embedding es un texto incrustado como punto en un espacio de
números. En la práctica, una lista de tamaño fijo (1024 números con bge-m3) para
cualquier texto, sea una pregunta de 6 palabras o un artículo de 300. Los números no se
interpretan uno a uno (no hay una dimensión de "plazos"); lo que tiene significado es la
posición relativa: textos que hablan de lo mismo quedan cerca.

El modelo de embeddings solo convierte texto en ese vector: no genera texto, no responde
y no busca. Por dentro:

```
"¿Me pagan por las prácticas?"
 1. Tokenizador: trocea en subpalabras y las convierte en números
    ["▁¿", "Me", "▁paga", "n", "▁por", "▁las", "▁práctica", "s", "?"] → [6, 2167, ...]
 2. Transformer (24 capas en bge-m3): cada token "mira" a los demás y obtiene un vector
    que depende del contexto ("práctica" no es igual que en "en la práctica")
 3. Pooling: resume los vectores de los tokens en uno solo (bge-m3 usa el del primer
    token, [CLS]; los e5 hacen la media)
 4. Normalización: el vector pasa a medir 1, y la similitud coseno es un producto escalar
→ [0.021, -0.113, ..., 0.045]   (1024 números)
```

La "inteligencia" está en el paso 2: el transformer se entrenó con millones de pares
pregunta-pasaje (aprendizaje contrastivo) para que la pregunta y su respuesta acaben
cerca. **Los chunks y las preguntas tienen que pasar por el mismo modelo**: cada modelo
construye su propio "mapa", y comparar vectores de dos modelos es como comparar
coordenadas de dos mapas distintos. Por eso habrá una colección por modelo.

### Apuntes: las piezas del paso
1. **Modelo de embeddings** (la decisión más importante):

| Modelo | Tamaño | Dimensiones | Límite de entrada | Notas |
|---|---|---|---|---|
| `intfloat/multilingual-e5-small` | ~470 MB | 384 | 512 tokens | Rápido; exige los prefijos `query:` y `passage:` |
| `intfloat/multilingual-e5-base` | ~1,1 GB | 768 | 512 tokens | Más preciso, mismos prefijos |
| `BAAI/bge-m3` | ~2,3 GB | 1024 | 8192 tokens | De los mejores multilingües abiertos; sin prefijos |
| APIs (OpenAI, Voyage...) | — | — | Largo | Clave de API y coste; la demo depende de un servicio externo |

   Anthropic no ofrece modelos de embeddings: Claude solo entra en el paso 7, para
   generar la respuesta.
2. **Base vectorial: Chroma.** Guarda id, vector, texto y metadatos de cada chunk y
   responde a "dame los k más parecidos", con filtros por metadatos. Con 122 vectores,
   una matriz de numpy iría igual de rápido; se usa Chroma por ser una herramienta
   estándar, persistente en disco y que escala si el corpus crece.
3. **Script `src/index.py`:** lee `chunks.json`, calcula los embeddings normalizados,
   recrea la colección desde cero (para que no queden restos de ejecuciones anteriores) y
   la guarda en `data/index/`.

### Decisiones
- **Modelo: `BAAI/bge-m3`.** Motivos:
  1. Calidad: en pruebas públicas de recuperación multilingüe (MIRACL, MTEB) está entre
     los mejores modelos abiertos.
  2. Límite de 8192 tokens: los chunks más largos (315 palabras + encabezado) rozan el
     límite de 512 de los e5, que cortarían el final sin avisar. **Medido después:** el
     chunk más largo tiene 486 tokens (los e5 usan el mismo tokenizador, XLM-RoBERTa), así
     que con e5 cabrían, pero con muy poco margen: cualquier encabezado más largo o un
     artículo nuevo los haría cortar.
  3. Sin prefijos: con e5, olvidar `query:`/`passage:` empeora el resultado sin dar error.
  4. "M3" = multifuncional: además del vector denso, genera pesos por palabra (parecido a
     BM25), útiles para la búsqueda híbrida del paso 8 sin añadir otro modelo.
  5. Licencia MIT.
- **Desventajas asumidas:** 568 M de parámetros frente a 118 M de e5-small; ~2,3 GB de
  descarga y 2-3 GB de memoria; varias veces más lento en CPU (indexar 122 chunks tarda
  un par de minutos y cada pregunta unas décimas de segundo; donde más se nota es en el
  arranque de la demo). Puede ser excesivo para un corpus tan pequeño: **no se sabe hasta
  medirlo**, y por eso e5 será el rival en el paso 8. Que admita 8192 tokens no significa
  que los chunks largos sean buenos: la dilución sigue existiendo.
- **Los embeddings se calculan con `sentence-transformers`** y se le pasan a Chroma, en
  lugar de usar su función de embeddings integrada: así se controla exactamente qué modelo
  se usa.
- **Distancia coseno** (Chroma usa la euclídea por defecto).
- **Metadatos simples:** Chroma solo admite texto, números o booleanos, así que
  `modificado_por` (lista) pasa a texto y `numero` se omite en las disposiciones (`None`).
- **Una colección por modelo** (`normativa_bge-m3`), para comparar modelos sin reindexar.

### Instalación
- `sentence-transformers` 6.3.0 y `chromadb` 1.5.9 desde PyPI. Unos 7 minutos: no por la
  descarga, sino por la instalación (PyTorch son miles de archivos que el antivirus revisa
  uno a uno, y Chroma arrastra ~100 dependencias porque también puede funcionar como
  servidor; aquí solo se usa en local).
- El modelo se descarga de Hugging Face la primera vez y queda en la caché del usuario
  (`~/.cache/huggingface`). En Windows sale un aviso de que no puede usar enlaces
  simbólicos en la caché: es inofensivo, solo ocupa algo más de disco.

### Resultado
`python src/index.py`: 122 chunks en la colección `normativa_bge-m3`, vectores de 1024
dimensiones, el chunk más largo con 486 tokens (límite 8192). Cargar el modelo tarda unos
3,5 s y calcular el embedding de una pregunta, unos 150 ms en CPU.

### Validación
El script comprueba que la colección tiene exactamente los ids de `chunks.json` y que
ningún chunk supera el límite de tokens del modelo (si no, se detiene con código 1).

### Primeras búsquedas (adelanto del paso 6)
Top 3 de 7 preguntas del conjunto de evaluación (✓ = artículo correcto):

| Pregunta | Resultado |
|---|---|
| ¿Cuántas horas a la semana se hacen de prácticas? | ✓ 1.º (art. 14) |
| Si la empresa me contrata al terminar, ¿me cuenta como antigüedad? | ✓ 1.º (art. 3) |
| Me puse malo y falté tres días, ¿tengo que recuperarlos? | ✓ 1.º (art. 14, parte 2: justo el trozo de las faltas) |
| ¿Cuánto tiempo tengo para presentar el TFG delante del tribunal? | ✓ 1.º (art. 22 ESI), pero el 2.º está a 0,002 |
| ¿Las prácticas en empresa se cobran? | ✓ 2.º (art. 20); 1.º el art. 14 (horario) |
| Si este curso no presento el TFG, ¿pierdo el tema y el tutor? | ✗ ninguno de los artículos correctos en el top 3 |
| ¿Cuánto cuesta matricularse del TFG? (sin respuesta) | Similitud máxima 0,495; el 1.º es "matrículas de honor" |

Lo que enseñan:
- **Las paráfrasis funcionan**: "me puse malo y falté" encuentra "faltas de asistencia
  derivadas de enfermedad común" sin compartir palabras.
- **El troceado ayuda**: en las faltas, el buscador trae justo la parte 2 del art. 14.
- **Las similitudes están muy apretadas** (0,55-0,68) y a veces separadas por milésimas.
  Su valor absoluto no significa mucho; lo que importa es el orden.
- **Primer fallo claro**: "¿pierdo el tema y el tutor?" no encuentra "Validez de la
  asignación". La pregunta habla de "tema y tutor" y el artículo de "asignación": es el
  tipo de caso que habrá que analizar en los pasos 6 y 8.
- **Falso amigo**: "matricularse" atrae "matrículas de honor". Un aviso de que los
  embeddings también se dejan llevar por las palabras.
- **Umbral de "no lo sé"**: la pregunta sin respuesta tiene una similitud máxima más baja
  (0,495), pero la respuesta correcta de "¿se cobran?" estaba en 0,549. Un umbral fijo
  sería frágil: la decisión de abstenerse tendrá que tomarla el LLM (paso 7).

### Apuntes: similitud coseno, distancia y normalización
La **similitud coseno** mide el ángulo entre dos vectores: vale 1 si apuntan en la misma
dirección (mismo significado), 0 si son perpendiculares (sin relación) y -1 si son
opuestos. Solo importa la dirección, no la longitud.

```
coseno(a, b) = (a · b) / (|a| · |b|)          a · b = a1·b1 + a2·b2 + ... + a1024·b1024
```

Ejemplo en 2 dimensiones: a = (0,6; 0,8) y b = (0,8; 0,6), los dos de longitud 1.
a · b = 0,6·0,8 + 0,8·0,6 = 0,96 → muy parecidos.

Si los vectores se **normalizan** (longitud 1) al guardarlos, el denominador vale 1 y el
coseno es solo el producto escalar: una multiplicación y una suma, muy rápido.

Chroma devuelve la **distancia** coseno = 1 − similitud: 0 es idéntico y cuanto más alta,
más lejos. Por eso para ordenar resultados se busca la distancia **más baja**. Con bge-m3
las similitudes salen apretadas (0,5-0,7): su valor absoluto no significa mucho, lo que
importa es el **orden**.

### Apuntes: búsqueda exacta y búsqueda aproximada (HNSW)
- **Búsqueda exacta** (fuerza bruta): comparar el vector de la pregunta con todos los
  vectores guardados y quedarse con los k mejores. Con 122 chunks son 122 productos
  escalares: instantáneo. Con millones sería lento.
- **Búsqueda aproximada** (*ANN, approximate nearest neighbours*): un índice que encuentra
  casi siempre los vecinos correctos sin compararlos todos. **HNSW** (*Hierarchical
  Navigable Small World*) organiza los vectores en un grafo por capas: las de arriba
  tienen pocos puntos y conexiones "largas", las de abajo todos los puntos y conexiones
  "cortas". La búsqueda entra por arriba y va bajando, saltando cada vez al vecino más
  cercano a la pregunta, como buscar una calle: primero el país, luego la ciudad, luego el
  barrio.
- Es lo que usa Chroma por defecto. Con nuestro corpus el resultado es el mismo que la
  búsqueda exacta; la ventaja aparecería con un corpus mucho mayor.

### Apuntes: cómo funciona `src/index.py`
- **`PREFIJOS`**: solo los e5 necesitan `passage: `/`query: `; para el resto, `.get` da
  prefijo vacío. Así el mismo script sirve para comparar modelos en el paso 8.
- **`nombre_coleccion`**: `"BAAI/bge-m3"` → `"normativa_bge-m3"` (una colección por modelo).
- **`metadatos`**: copia los campos simples, convierte `modificado_por` (lista) en texto y
  omite `numero` en las disposiciones. Se omite en vez de poner un valor falso como -1,
  que podría confundirse con un número real al filtrar.
- **`contar_tokens`**: tokeniza sin cortar (`truncation=False`) para saber la longitud
  real de cada chunk, contando los tokens especiales de inicio y fin.
- **`indexar`**:
  1. Comprueba los tokens **antes** de calcular nada: si algo se fuera a cortar, falla
     pronto.
  2. `encode(..., normalize_embeddings=True, batch_size=8)` devuelve una matriz de
     122 × 1024. Los textos se procesan de 8 en 8: más lotes grandes van más rápido pero
     gastan más memoria.
  3. `PersistentClient` guarda la base en disco (`data/index/`, un SQLite y los ficheros
     del índice).
  4. Borra la colección si existe y la crea de nuevo: ejecutar el script dos veces da el
     mismo resultado (idempotencia).
  5. `configuration={"hnsw": {"space": "cosine"}}`: HNSW es el índice que usa Chroma para
     buscar vecinos rápido sin comparar con todos (un grafo por capas). Con 122 vectores
     no hace falta, pero es lo que escala. Chroma devuelve la **distancia** coseno
     (1 − similitud).
  6. Los metadatos de la colección guardan el modelo y las dimensiones: al buscar se
     podrá comprobar que la pregunta usa el mismo modelo que los chunks.
  7. `add` guarda ids, vectores, `documents` (el `texto` de la norma, que es lo que verá
     el LLM, no el `texto_embedding` con el encabezado) y metadatos.
- **`comprobar`**: `get(include=[])` devuelve solo los ids; deben coincidir exactamente
  con los de `chunks.json`.

### Apuntes: qué es Chroma y qué guarda
**Chroma** es una base de datos vectorial **embebida**: una librería que funciona dentro
del propio proceso de Python (sin servidor), como SQLite pero pensada para vectores. Tiene
tres partes: almacenamiento en disco, un índice para buscar vecinos rápido (HNSW) y una
API (`add`, `get`, `query`, `delete`).

Jerarquía:
```
PersistentClient (data/index/)            ← la base de datos
└── colección "normativa_bge-m3"          ← como una tabla; una por modelo
    ├── metadata: {modelo: BAAI/bge-m3, dimensiones: 1024}
    ├── configuration: {space: cosine, max_neighbors: 16, ...}   ← ajustes del índice HNSW
    └── 122 registros, cada uno con:
        ├── id          "practicas_uca_2012_art_14_p2"
        ├── embedding   [-0.0297, 0.0143, -0.0394, ...]  (1024 números, longitud 1)
        ├── document    "3. En el caso de prácticas extracurriculares, ..."  (el texto de la norma)
        └── metadata    {documento, titulo, numero: 14, parte: 2, apartados: "3", url, ...}
```

En disco: `chroma.sqlite3` guarda las colecciones, ids, textos, metadatos y el registro de
los vectores; la carpeta con nombre UUID guarda el índice HNSW (los vectores organizados
en un grafo para buscar sin compararlos todos).

**`vectores.tolist()`**: `encode` devuelve una matriz de **numpy** (`ndarray`, números
`float32` de 4 bytes en un bloque contiguo de memoria, 122 × 1024). `.tolist()` la
convierte en listas normales de Python (122 listas de 1024 `float`), el formato que
acepta la API de Chroma sin ambigüedad. Al convertir, cada `float32` pasa a `float` de
Python (64 bits): por eso 0.1234567 aparece como 0.12345670163631439, que es el valor
exacto que podía guardar el `float32`.

### Pendiente
- Paso 6: `src/retrieve.py` (buscar los k chunks de una pregunta) y `src/evaluate.py`
  (Recall@k y MRR sobre todo el conjunto de evaluación).

## 2026-11-26 · Sesión 10: recuperación y evaluación (paso 6)

### Apuntes: qué se hace en este paso
Dos scripts:
- **`src/retrieve.py`**, el buscador: recibe una pregunta y devuelve los k chunks más
  parecidos con su texto, metadatos y similitud. Calcula el embedding de la pregunta con
  **el mismo modelo** que indexó la colección (lo lee de sus metadatos) y le pone el
  prefijo de pregunta si el modelo lo necesita. Lo reutilizarán el paso 7 (generación) y
  la app.
- **`src/evaluate.py`**, la medición: pasa todas las preguntas del conjunto de evaluación
  por el buscador, compara lo recuperado con sus fuentes y calcula las métricas, en total y
  por tipo de pregunta. También lista los fallos para analizarlos y guarda los resultados
  para poder comparar experimentos.

Un chunk cuenta como acierto si pertenece a una de las fuentes de la pregunta: se le quita
el sufijo `_p1`/`_p2` al id y se compara con la lista de fuentes.

### Apuntes: las métricas
Ejemplo: pregunta con fuentes {art. 20, art. 25}; el buscador devuelve, en orden,
[art. 14, art. 20, art. 3, art. 25, art. 22].

- **Acierto@k** (*hit rate*): ¿hay al menos una fuente correcta entre los k primeros?
  Acierto@1 = 0 (el primero es el 14), Acierto@3 = 1 (el 20 está 2.º).
- **Recall@k**: qué fracción de las fuentes aparece entre los k primeros.
  Recall@3 = 1/2 (solo el 20), Recall@5 = 2/2. Importa en las preguntas `multi` y
  `ambigua`: si solo llega uno de los dos reglamentos, la respuesta será incompleta.
- **MRR** (*Mean Reciprocal Rank*): 1 / posición de la primera fuente correcta (1.º → 1,
  2.º → 0,5, 3.º → 0,33...; 0 si no aparece), promediado sobre todas las preguntas. Mide
  si lo correcto sale **arriba**: el LLM presta más atención a lo primero y, si se usa un k
  pequeño, lo que va abajo se pierde. En el ejemplo, 1/2 = 0,5.

Se calculan para varios k (1, 3, 5, 10). La curva dice cuántos chunks hay que pasarle al
LLM en el paso 7: un k más alto recupera más, pero mete más ruido y cuesta más tokens.

Las preguntas `sin_respuesta` no entran en estas métricas (no tienen fuentes). Se guarda
su similitud máxima para comprobar si se distinguen de las demás (en el paso 5 ya se vio
que un umbral fijo es frágil).

### Apuntes: línea base y análisis de fallos
Los primeros números son la **línea base**: cada mejora del paso 8 (búsqueda híbrida,
*reranker*, otro modelo, otro troceado) se compara contra ellos. Por eso se guardan con
su configuración (modelo, k, fecha).

Cada fallo tiene una de estas causas, y cada una tiene un arreglo distinto:
1. **La fuente faltaba en la pregunta**: el buscador trajo un artículo que también
   respondía. Se corrige `questions.json`, no el sistema.
2. **Diferencia de vocabulario**: la pregunta y el artículo dicen lo mismo con palabras
   distintas ("¿pierdo el tema y el tutor?" frente a "validez de la asignación").
   Posibles arreglos: búsqueda híbrida, reformular la pregunta, otro modelo.
3. **Confusión entre documentos**: trae el artículo equivalente del otro reglamento
   (marco UCA frente a ESI). Posibles arreglos: filtros por metadatos, un k mayor.
4. **Ranking**: el correcto está, pero abajo. Posible arreglo: un *reranker* (un segundo
   modelo que reordena los candidatos leyendo la pregunta y el chunk juntos).

Riesgo: ajustar el sistema hasta acertar estas preguntas concretas (*sobreajuste*). Las
mejoras deben tener sentido general, y las 10 preguntas nuevas del final lo comprobarán.

### Apuntes: qué hace exactamente el buscador y en qué se diferencia de la evaluación
**La pregunta no se trocea.** Es corta, así que entera se convierte en **un solo vector**
con el mismo modelo que los chunks. Los vectores de los 122 chunks ya están calculados y
guardados desde el paso 5; en cada pregunta no se recalculan.

```
"¿Las prácticas se cobran?"
  1. modelo.encode → 1 vector de 1024 números (≈150 ms)
  2. Chroma compara ese vector con los 122 guardados (similitud coseno)
       art_20 → 0,549   art_14_p1 → 0,553   art_3 → 0,546   tfgm_esi_art_7 → 0,31 ...
  3. Ordena de mayor a menor similitud y se queda con los k primeros
  4. Devuelve, de cada uno: id, texto, metadatos y similitud
```

| | `retrieve.py` (buscador) | `evaluate.py` (examen) |
|---|---|---|
| Qué recibe | Una pregunta cualquiera | Las preguntas de `questions.json` con sus fuentes |
| Qué sabe | Nada de la respuesta correcta | La respuesta correcta (las fuentes) |
| Qué hace | Busca y devuelve los k chunks | Llama al buscador con cada pregunta, compara con las fuentes y calcula métricas |
| Quién lo usa | El paso 7 y la app (preguntas reales) | Solo el desarrollador, para medir |

Es la diferencia entre el **alumno** que responde y el **profesor** que corrige con la
plantilla: `evaluate.py` no busca por su cuenta, usa `retrieve.py` tal cual. Así se mide
exactamente el mismo buscador que usarán los usuarios.

### Qué he hecho
- **`src/retrieve.py`**: clase `Buscador`, que abre la colección, lee de sus metadatos qué
  modelo la creó y lo carga una sola vez (tarda unos segundos); `buscar(pregunta, k,
  filtro)` calcula el embedding de la pregunta y devuelve los k chunks con id, unidad
  (artículo sin `_pN`), similitud, texto y metadatos. Desde la consola:
  `python src/retrieve.py "¿Las prácticas se cobran?" -k 3 --documento practicas_uca_2012`.
- **`src/evaluate.py`**: pasa las 62 preguntas por el buscador (top 10), calcula Acierto@k,
  Recall@k y MRR en total y por tipo, compara la similitud máxima de las preguntas con y sin
  respuesta, lista los fallos y guarda todo en `eval/resultados/normativa_bge-m3.json`.

### Apuntes: cómo funcionan `retrieve.py` y `evaluate.py`
**`retrieve.py`**
- `unidad(id)`: quita el sufijo `_p1`, `_p2`... con una expresión regular
  (`practicas_uca_2012_art_14_p2` → `practicas_uca_2012_art_14`), para comparar chunks con
  las fuentes, que son artículos.
- `Buscador.__init__`: abre la colección, lee de sus metadatos el modelo que la creó, lo
  carga **una sola vez** y prepara el prefijo de pregunta (vacío en bge-m3). Es una clase
  para que la carga lenta (segundos) no se repita en cada búsqueda.
- `Buscador.buscar(pregunta, k, filtro)`: embedding normalizado de la pregunta →
  `coleccion.query(...)` → Chroma devuelve listas paralelas (ids, distancias, textos,
  metadatos) **por cada pregunta enviada**, por eso el `[0]` → se juntan en un diccionario
  por resultado, con `similitud = 1 − distancia`. `filtro` se pasa como `where` (por
  ejemplo `{"documento": "tfgm_esi"}`) y Chroma solo compara con esos chunks.
- `cita(resultado)`: texto legible para mostrar ("Art. 22 (apartados 7-14) · practicas_uca_2012").
- `main`: argumentos de consola (pregunta, `-k`, `--documento`, `--modelo`) e impresión.

**`evaluate.py`**
- `puntuar(recuperados, fuentes)`: métricas de **una** pregunta. Para cada k corta la
  lista de artículos recuperados, hace la intersección con las fuentes y calcula Acierto@k
  (¿alguna?) y Recall@k (¿qué fracción?). La posición de la primera fuente correcta da el
  rango recíproco (1/posición).
- `media(filas)`: media de cada métrica en un grupo de preguntas; la media del rango
  recíproco es el MRR.
- `tabla(grupos)`: formatea la tabla de resultados.
- `main`: crea **un** buscador, recupera el top 10 de cada pregunta (una sola búsqueda
  sirve para calcular todos los k), puntúa las que tienen fuentes, agrupa por tipo,
  compara la similitud máxima con y sin respuesta, lista los fallos (ninguna fuente en el
  top 5) y las preguntas incompletas, y guarda configuración, métricas y detalle en
  `eval/resultados/<colección>.json`.

### Resultado: línea base (bge-m3, troceado B, sin mejoras)

| | n | Acierto@1 | Acierto@3 | Acierto@5 | Acierto@10 | Recall@5 | MRR |
|---|---|---|---|---|---|---|---|
| **TOTAL** | 57 | 72 % | 86 % | **91 %** | 91 % | 72 % | 0,79 |
| ambigua | 11 | 73 % | 82 % | 82 % | 82 % | **37 %** | 0,76 |
| cifra | 11 | 73 % | 91 % | 91 % | 91 % | 77 % | 0,80 |
| directa | 15 | 87 % | 93 % | 93 % | 93 % | 90 % | 0,90 |
| multi | 7 | 57 % | 71 % | 100 % | 100 % | 73 % | 0,69 |
| parafrase | 13 | 62 % | 85 % | 92 % | 92 % | 77 % | 0,75 |

~240 ms por pregunta en CPU.

- En 9 de cada 10 preguntas llega al menos un artículo correcto entre los 5 primeros, y en
  7 de cada 10 sale el primero.
- Pasar de k=5 a k=10 no recupera nada más: lo que no está en el top 5 no está tampoco en el
  top 10. Ampliar k no es la solución; para el paso 7, k=5 es suficiente.
- Las `cifra` funcionan mejor de lo que esperaba (91 %): las preguntas mencionan el tema
  ("horas a la semana", "duración") y eso basta para encontrar el artículo.
- **El punto débil son las `ambigua`: Recall@5 del 37 %.** Casi nunca llegan los dos
  reglamentos a la vez.
- **"No lo sé"**: la similitud del primer resultado tiene una mediana de 0,645 en las
  preguntas con respuesta y 0,545 en las que no la tienen, pero se solapan (mínimo 0,512
  con respuesta, máximo 0,604 sin ella). Confirmado: un umbral fijo no sirve; lo decidirá el
  LLM.

### Análisis de los fallos
5 preguntas sin ninguna fuente en el top 5:

| Pregunta | Causa |
|---|---|
| q010 ¿Qué aspectos se tienen en cuenta en la calificación del TFG según el reglamento marco? | Confusión entre documentos: trae artículos de la ESI |
| q035 ¿Qué nota necesita un TFG para que lo suban al repositorio? | Confusión entre documentos: trae artículos de la ESI |
| q048 Si no presento el TFG, ¿pierdo el tema y el tutor? | Vocabulario ("tema y tutor" frente a "asignación") y documentos |
| q049 ¿Puedo hacer el TFG junto a un compañero? | Vocabulario ("compañero" frente a "grupo de alumnos") y documentos |
| q025 ¿Quién me va a supervisar dentro de la empresa? | Vocabulario ("empresa" frente a "entidad colaboradora", "supervisar" frente a "tutor") |

Ninguno es un error del conjunto de evaluación (los artículos recuperados no responden).

**Hallazgo principal: el reglamento marco nunca usa la sigla "TFG"** (0 apariciones; dice
"trabajos de fin de grado"), mientras que el de la ESI la usa 159 veces. Como los alumnos
preguntan diciendo "TFG", los chunks de la ESI ganan casi siempre: en los top 5 de las
preguntas sobre TFG hay 141 chunks de la ESI y solo 12 del marco. En las 11 preguntas
`ambigua`, los 5 primeros resultados son **siempre** de la ESI. Las preguntas del marco que
sí aciertan son las que dicen "trabajo fin de grado" o "reglamento marco".

Es un caso de libro de cómo el vocabulario de un documento condiciona la recuperación, y
el primer objetivo del paso 8. Hipótesis a probar:
1. Añadir la sigla al nombre del marco en el encabezado de contexto
   ("... de trabajos fin de grado y fin de máster (TFG/TFM)").
2. Recuperar por separado de cada reglamento de TFG (filtro por documento) y juntar los
   resultados, para garantizar que llegan los dos.
3. Búsqueda híbrida o un *reranker*.

### Pendiente
- Paso 7: generación de la respuesta con el LLM a partir de los 5 primeros chunks.
- Paso 8: atacar la confusión entre el marco y la ESI (hipótesis de arriba).

## 2026-11-26 · Sesión 11: generación de respuestas (paso 7)

### Apuntes: qué se hace en este paso
Hasta el paso 6 el sistema **encuentra** los artículos; en el 7 **responde**:

```
pregunta → retrieve.py (top 5 chunks) → prompt = instrucciones + chunks numerados + pregunta
         → LLM → respuesta en español con citas [1], [2]... o "no lo encuentro en la normativa"
```

`src/generate.py` monta el prompt, llama al LLM y devuelve la respuesta con sus fuentes.
El LLM no busca nada: solo lee los chunks que le pasamos. Si el artículo correcto no llega
(el 9 % de las preguntas en la línea base), no puede responder bien; por eso la
recuperación se midió antes.

### Apuntes: qué hace exactamente el LLM (y qué no)
El LLM **no consulta el RAG ni busca nada por su cuenta**: no tiene acceso a Chroma, ni a
los PDFs, ni a internet. Todo lo hace nuestro código, y el LLM solo recibe **un texto** y
devuelve **otro texto**:

```
generate.py (en tu ordenador)                         Gemini (servidores de Google)
─────────────────────────────                         ─────────────────────────────
1. retrieve.py busca los 5 chunks en Chroma
2. monta UN texto: instrucciones + chunks + pregunta
3. lo envía por la API  ───────────────────────────►  4. lee el texto completo
                                                       5. escribe la respuesta palabra a
                                                          palabra (predice el siguiente token)
6. recibe la respuesta  ◄───────────────────────────
7. la muestra con sus citas
```

- **No tiene memoria entre llamadas:** cada pregunta es una petición independiente; lo
  único que "sabe" de la normativa es lo que va en ese texto.
- **Sí tiene conocimiento propio**, aprendido en su entrenamiento (guardado en sus pesos),
  y ahí está el riesgo: podría mezclar lo que recuerda de otras universidades o de leyes
  antiguas. Por eso el prompt le exige responder solo con los fragmentos, y la evaluación
  mide la **fidelidad**.
- Algunos LLM pueden usar herramientas (buscar en la web, ejecutar código) si se las das;
  aquí no se le da ninguna, a propósito.

### Apuntes: las decisiones del paso
1. **Qué LLM.** Por API (Claude) o local (por ejemplo, con Ollama).
   - API: mejor calidad siguiendo instrucciones (citar, no inventar, español), rápido, y la
     demo en Hugging Face funciona sin GPU. Hace falta una clave de API (variable de entorno,
     nunca en el código) y cuesta dinero por uso. Precios por millón de tokens
     (entrada / salida): Opus 5.5 4 $ / 20 $, Sonnet 5.5 2 $ / 10 $, Haiku 5.5 0,10 $ / 0,50 $.
     Una pregunta son unos 2.000-2.500 tokens de entrada (5 chunks + instrucciones) y unos
     cientos de salida.
   - Local: gratis y privado, pero hay que descargar un modelo de varios GB, en CPU tarda
     de segundos a minutos por respuesta, los modelos pequeños siguen peor las reglas y la
     demo gratuita de Hugging Face no podría ejecutarlo.
   - El código dejará el modelo como parámetro, para poder cambiarlo y comparar.
2. **El prompt.** Instrucciones (*system prompt*): responder solo con la información de
   los fragmentos, citar cada afirmación con su número, decir que no está en la normativa
   si no lo está (en lugar de inventar), y si el reglamento marco y el de la ESI dicen
   cosas distintas, explicar los dos e indicar que el de la ESI es el específico para sus
   estudiantes. Cada fragmento va etiquetado con su cita (documento, artículo, apartados) y,
   si procede, la modificación que le dio su redacción actual.
3. **Formato de salida.** Texto libre con marcas [n], o **salida estructurada** (JSON con
   la respuesta, las fuentes usadas y si ha encontrado la información). La estructurada
   facilita evaluar y mostrar las fuentes en la app.

### Apuntes: cómo se evalúa la generación
Es más difícil que evaluar la recuperación, porque la respuesta es texto libre. Se mide:
1. **Abstención:** ¿dice "no lo encuentro" en las preguntas `sin_respuesta`? ¿Y no lo dice
   cuando sí hay respuesta?
2. **Citas:** ¿las fuentes que cita están entre las fuentes correctas de la pregunta?
3. **Corrección:** ¿coincide con la respuesta de referencia? Se usa otro LLM como juez
   (*LLM-as-a-judge*), que compara la respuesta con la de referencia y la clasifica como
   correcta, parcial o incorrecta. El juez también se equivoca: hay que revisar una muestra
   a mano.
4. **Fidelidad** (*faithfulness*): ¿todo lo que afirma está en los fragmentos que recibió?
   Una respuesta puede ser "correcta" por conocimiento propio del LLM y no por los
   documentos, y eso es justo lo que no queremos.

Cada evaluación completa son unas 62 llamadas para generar más 62 para juzgar, así que
tiene un coste por ejecución que hay que tener en cuenta.

### Decisiones
- **LLM: Gemini (modelo Flash) en su nivel gratuito**, por API. Alternativas valoradas:
  Claude (sin nivel gratuito; con Haiku 5.5 el proyecto entero costaría menos de 1 $),
  OpenAI (sin saldo disponible), Groq (gratuito, modelos abiertos algo menos fiables
  siguiendo instrucciones) y OpenRouter (50 peticiones al día, insuficiente para evaluar).
  Una evaluación completa son unas 124 llamadas (62 para responder y 62 para juzgar), y el
  nivel gratuito de Gemini las cubre.
- **¿Es suficiente un modelo "Flash"?** La tarea no exige conocimiento propio del modelo:
  es comprensión lectora de 5 fragmentos cortos en español, siguiendo reglas (citar,
  abstenerse, contrastar el marco con la ESI). Es justo lo que hacen bien los modelos
  rápidos actuales. Lo difícil será la abstención y las preguntas ambiguas, y eso lo dirá
  la evaluación, no la intuición.
- **Precauciones:** en el nivel gratuito Google puede usar lo que se envía para mejorar sus
  productos (aquí solo va normativa pública y preguntas de ejemplo); los límites y los
  nombres de los modelos cambian, así que el modelo será un parámetro; la clave va en un
  archivo `.env` (ignorado por git), nunca en el código.

### Qué he hecho
- Clave de Gemini creada en Google AI Studio (proyecto "Default Gemini Project") y
  guardada en `.env`, que git ignora. La clave no se escribe en ningún otro sitio: ni en
  el código, ni en el chat.
- Instalada la librería `google-genai`.
- **Prueba de modelos en el nivel gratuito:** los Flash completos (3.5, 3.6, 3.7, 3.8)
  respondían "alta demanda" (503) de forma persistente, y 2.5 Flash ya no está disponible
  (404). Los Flash-Lite sí responden (~1,5 s). Modelo por defecto: `gemini-3.5-flash-lite`,
  con `gemini-3.1-flash-lite` de reserva.
- **`src/generate.py`**: busca los 5 chunks, monta el prompt (instrucciones + fragmentos
  numerados con su cita + pregunta) y pide una **salida estructurada** con un esquema de
  pydantic: `encontrado` (bool), `respuesta` (texto con citas [n]) y `fuentes` (números de
  los fragmentos usados). Temperatura 0 para que sea lo más estable posible. Si el nivel
  gratuito responde 503 o 429, reintenta con espera creciente (5, 10, 20 s) y después
  prueba el modelo de reserva. Descarta números de fuente que no existan.

### Primeras respuestas
- "¿Las prácticas en empresa se cobran?" → distingue curriculares (la empresa *podrá*
  pagar) y extracurriculares (pagará lo previsto en la oferta), aclara que no es una nómina
  y cita los arts. 20 y 3. Correcta.
- "Me puse malo y falté tres días..." → no hay que recuperarlas si están justificadas y
  no superan 15 días no consecutivos o 5 consecutivos; cita el art. 14, apartado 3.
  Correcta.
- "¿Cuánto cuesta matricularse del TFG?" → `encontrado: false`, "no aparece en la
  normativa consultada". **Se abstiene bien**, sin inventar un precio.
- "¿Puedo escribir y defender el TFG en inglés?" → correcta según la ESI (art. 17), pero
  **no menciona el reglamento marco**, porque el buscador no lo recuperó: el problema del
  "TFG" del paso 6 se arrastra a la respuesta, como era de esperar.

### Pendiente
- Evaluar la generación sobre todo el conjunto: abstención, citas, corrección (con un LLM
  como juez) y fidelidad.

### Apuntes: por qué un LLM como juez, si también se equivoca
Para evaluar texto libre hay cuatro opciones:

| Opción | Problema |
|---|---|
| Corregir a mano las 62 respuestas | Fiable, pero hay que repetirlo en cada experimento del paso 8: no escala |
| Métricas de coincidencia de palabras (exact match, BLEU, ROUGE) | Penalizan una respuesta correcta dicha con otras palabras y premian una que copia palabras pero se equivoca |
| Similitud de embeddings entre respuesta y referencia | Mide si hablan del mismo tema, no si el dato es correcto ("25 horas" frente a "20 horas" sale casi igual) |
| **LLM como juez** | Entiende el significado y escala, pero tiene sesgos: indulgencia, preferencia por respuestas largas, inconsistencia y preferencia por textos de su misma familia de modelos |

Se elige el juez, pero acotando dónde puede equivocarse:
1. **Lo que se puede medir con código no lo juzga el LLM.** La abstención (campo
   `encontrado`) y las citas (fuentes citadas frente a las fuentes de la pregunta) se
   calculan de forma exacta.
2. **El juez no evalúa en abstracto:** recibe la pregunta, la **respuesta de referencia**
   y los fragmentos, y solo compara. Comparar con una referencia es mucho más fácil y
   fiable que decidir desde cero si algo es correcto.
3. **Rúbrica cerrada y salida estructurada:** correcta / parcial / incorrecta, y
   fiel / no fiel, siempre con una justificación breve. Temperatura 0.
4. **Calibración humana:** se corrige a mano una muestra (unas 15 respuestas) y se mide
   cuántas veces coincide el juez. Si coincide en la gran mayoría, sus cifras agregadas
   son creíbles; si no, se ajusta la rúbrica. El porcentaje de acuerdo se publica junto a
   los resultados.
5. **Se usa sobre todo para comparar:** el mismo juez mide dos configuraciones, así que
   sus errores afectan a las dos por igual y la diferencia entre ellas es más fiable que
   la cifra absoluta.

Limitación conocida: con el nivel gratuito, el juez es de la misma familia que el modelo
que responde (Gemini Flash-Lite), y eso puede hacerlo más indulgente. Una alternativa
para el paso 8 es un juez de otra familia (por ejemplo, un modelo abierto en Groq).

### Apuntes: cómo funciona `src/evaluate_generation.py`
- **`INSTRUCCIONES_JUEZ` y `Veredicto`:** la rúbrica del juez (correcta / parcial /
  incorrecta, fiel sí/no) y el esquema de su salida. La justificación va **primero** en el
  esquema para que el juez razone antes de decidir.
- **`juzgar`:** monta el prompt del juez (pregunta, referencia, respuesta del sistema y
  fragmentos) y reutiliza `llamar` de `generate.py` con otras instrucciones y otro esquema.
- **`evaluar_una`:** genera la respuesta con `responder`. Si la pregunta no tiene fuentes,
  solo comprueba con código que se ha abstenido (sin juez). Si las tiene, comprueba que
  **no** se ha abstenido, cuenta las citas correctas y llama al juez.
- **`resumen`:** abstención bien en las `sin_respuesta`, falsas abstenciones, precisión de
  las citas, porcentaje que cita algo correcto, reparto correcta/parcial/incorrecta y
  fidelidad, en total y por tipo.
- **`crear_calibracion`:** muestra de 15 respuestas, repartida por tipos, con semilla fija
  (siempre la misma), en un CSV con `;` y `utf-8-sig` para que Excel lo abra bien, y
  **sin** el veredicto del juez para no influir en la corrección humana.
- **`acuerdo`:** cruza por id la corrección humana con la del juez, da el porcentaje de
  acuerdo y lista los desacuerdos con la justificación del juez.
- **`main`:** reanuda el progreso guardado (las llamadas gratuitas pueden cortarse), guarda
  después de cada pregunta, espera unos segundos entre llamadas por el límite por minuto
  y al final escribe métricas y detalle en `eval/resultados/generacion_<modelo>.json`.

### Resultado: evaluación de la generación (Gemini 3.5 Flash-Lite, k=5)

| Métrica | Valor | Cómo se mide |
|---|---|---|
| Abstención correcta en preguntas sin respuesta | **100 %** (5/5) | código |
| Falsas abstenciones (dice que no está, pero sí está) | 11 % (6/57) | código |
| Precisión de las citas | 91 % | código |
| Cita al menos un artículo correcto | 91 % | código |
| Corrección | correcta 72 % · parcial 18 % · incorrecta 11 % | juez + código |
| Fidelidad | 96 % | juez |

Por tipo (corrección correcta / parcial / incorrecta): ambigua 55/27/18, cifra 73/9/18,
directa 73/20/7, multi 71/29/0, parafrase 85/8/8.

Unas 125 llamadas gratuitas, sin ningún corte por límite.

### Análisis
- **El LLM no se inventa nada cuando el buscador falla.** 5 de las 6 falsas abstenciones
  son exactamente las 5 preguntas en las que el buscador no trajo ningún artículo correcto
  (paso 6): sin la información, dice "no aparece en la normativa consultada" en vez de
  rellenar. Los errores de punta a punta son, casi todos, errores de **recuperación**. La
  sexta (q053, créditos del TFG) es un caso límite: dice que no hay una cifra exacta y da
  el matiz correcto, pero marca `encontrado = false`.
- **Fidelidad del 96 %:** solo 2 respuestas añaden algo que no estaba en los fragmentos.
- **Las ambiguas son las peores** (55 % correctas): como el buscador casi nunca trae el
  reglamento marco, el LLM responde solo con el de la ESI.

### El juez es indulgente (lo que se temía)
Revisando sus veredictos:
1. En 3 falsas abstenciones (q010, q049, q053) puso "correcta" porque el sistema fue
   "fiel a lo que leyó", aunque la rúbrica dice que abstenerse cuando la referencia sí da
   la respuesta es "incorrecta". Confunde fidelidad con corrección. **Corregido con
   código:** una abstención en una pregunta con respuesta cuenta siempre como incorrecta
   (de 77 % a 72 % de correctas).
2. En varias ambiguas (q045, q046, q047, q050, q060) puso "correcta" a respuestas que solo
   explican el reglamento de la ESI, cuando la referencia incluye los dos reglamentos. Según
   la rúbrica deberían ser "parcial". Esto no se corrige a ojo: lo decidirá la
   **calibración humana** (q047 y q060 están en la muestra).

### Calibración
`python src/evaluate_generation.py --calibracion` → `eval/calibracion.csv` con 15
respuestas (q001, q004, q012, q016, q017, q020, q031, q032, q034, q042, q044, q047, q058,
q060, q061), sin el veredicto del juez. Pendiente: corregirlas a mano y medir el acuerdo
con `--acuerdo`.

### Apuntes: cómo sabe el LLM si la respuesta está en los fragmentos
- **Al LLM no le llegan vectores, le llegan textos.** Los embeddings solo sirven para
  *buscar* (comparar la pregunta con los chunks en Chroma). Lo que se envía a Gemini es el
  texto de los 5 chunks, numerados, más la pregunta. Tampoco le pasamos la similitud.
- **No lo "sabe" con ninguna comprobación: lo juzga leyendo**, como un estudiante en un
  examen de comprensión lectora. Lee la pregunta y los fragmentos y decide si alguno la
  responde. Lo empujamos con la regla 3 del prompt ("si no está, encontrado = false; no lo
  deduzcas") y con el campo `encontrado` de la salida estructurada.
- **Lo hace bien, pero puede fallar en los dos sentidos:**
  - *Falsa abstención:* la respuesta está y dice que no (q053, créditos del TFG).
  - *Falso positivo:* da por buena información que parece responder pero es de otro
    contexto. Por ejemplo, responde con el reglamento de la ESI a una pregunta sobre el
    marco. Es más peligroso, porque la respuesta suena segura.
- **No puede saber lo que no le llega.** Si el buscador trae solo la ESI, el LLM no tiene
  forma de saber que el marco dice otra cosa. Por eso las preguntas ambiguas son las más
  flojas: el fallo está en la recuperación, no en la lectura.
- **El orden influye un poco.** Los LLM tienden a atender más al principio y al final del
  contexto que al medio ("lost in the middle"). Con 5 fragmentos cortos el efecto es
  pequeño, pero existe.
- **Lo que dicen nuestros datos:** abstención correcta en el 100 % de las preguntas sin
  respuesta, y 5 de las 6 falsas abstenciones coinciden con los 5 fallos del buscador.
  Cuando no le llega la información, lo detecta y no se la inventa.

### Apuntes: cómo usan RAG los asistentes como Claude o ChatGPT
- **Un LLM no está "siempre al día".** Su conocimiento se congela en la fecha de corte de
  su entrenamiento, y no aprende de las conversaciones. Lo que sabe está guardado de forma
  difusa en sus pesos: puede recordar "más o menos" un reglamento, pero no citar el
  artículo exacto, y puede mezclarlo con el de otra universidad.
- **Para qué sirve entonces el RAG:**
  1. **Información nueva:** normativa publicada después del corte.
  2. **Información privada o de nicho:** documentos de una empresa, o un reglamento de una
     escuela que casi no aparece en internet.
  3. **Citas verificables:** el usuario puede comprobar el artículo exacto, cosa que la
     memoria del modelo no permite.
  4. **Menos alucinaciones:** el modelo copia de un texto delante en vez de reconstruir de
     memoria.
- **Cómo lo hacen los asistentes (en general):** con **herramientas**. El modelo decide
  buscar en la web, leer un archivo o consultar documentos subidos, el sistema le devuelve
  el texto encontrado y responde con él. Es "RAG agéntico": el modelo decide cuándo y qué
  buscar, y puede buscar varias veces. Claude Code, por ejemplo, recupera información con
  búsquedas de texto (grep) y leyendo archivos, sin embeddings. Nuestro RAG es el "clásico":
  el código siempre busca una vez y el modelo no elige.
- **¿A qué da más importancia, al contexto o a su memoria?** Están entrenados para
  apoyarse en el contexto que se les da, pero no es una regla absoluta. Si el contexto
  contradice algo que el modelo "cree saber", a veces gana su memoria (se llama *conflicto
  de conocimiento*). Por eso nuestro prompt dice "aunque creas saber la respuesta", y por
  eso medimos la fidelidad.
- **Alternativa: meterlo todo en el contexto.** Nuestro corpus son 122 chunks y unas
  16 600 palabras (unos 25 000 tokens, a ojo), y cabe entero en el contexto de Gemini. Para
  un corpus tan pequeño sería una alternativa real: no hay fallos de recuperación, porque
  el modelo lo lee todo. El RAG gana en coste y rapidez por pregunta, escala a miles de
  documentos, da citas precisas y no sufre el "lost in the middle" con contextos enormes.
  Comparar las dos opciones es un buen experimento para el paso 8.
