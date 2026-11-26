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

### Pendiente
- Paso 4: escribir el conjunto de evaluación (40-60 preguntas con su artículo correcto)
  antes de indexar, para poder medir cada decisión.
