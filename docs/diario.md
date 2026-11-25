# Diario de desarrollo

Registro de lo que hago en cada sesión, las decisiones que tomo y por qué,
y los problemas que encuentro.

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
- **Opción A (expresiones regulares) como base**, con la opción B (negrita del PDF) como
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

### Pendiente
- Escribir `data/parches.json` con los cambios de 2014 y 2015 y aplicarlos para obtener
  el texto consolidado.
