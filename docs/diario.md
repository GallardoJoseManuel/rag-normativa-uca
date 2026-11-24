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