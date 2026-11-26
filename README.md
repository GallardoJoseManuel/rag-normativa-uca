# rag-normativa-uca

Asistente que responde preguntas sobre la normativa de Trabajos Fin de Grado/Máster y de
prácticas externas de la Universidad de Cádiz, citando el documento y el artículo de donde
saca cada respuesta. Si la información no está en los documentos, lo dice en lugar de
inventarla.

> **Estado:** en desarrollo. El proceso completo, con las decisiones y los problemas
> encontrados, está documentado en el [diario de desarrollo](docs/diario.md).

## Cómo funciona

El proyecto es un sistema RAG (*Retrieval-Augmented Generation*): en lugar de pedirle a un
LLM que responda de memoria, primero se buscan los fragmentos de la normativa relacionados
con la pregunta y se le pasan junto con ella.

**Indexación** (una vez, o cuando cambian los documentos):

```
PDFs → extraer texto → limpiar → trocear en chunks → calcular embeddings → base vectorial
```

**Consulta** (cada pregunta):

```
pregunta → embedding → buscar los chunks más cercanos → prompt con los chunks → LLM → respuesta con citas
```

## Hoja de ruta

| # | Paso | Qué se hace | Archivo | Estado |
|---|---|---|---|---|
| 0 | Preparación | Repositorio, entorno, corpus, `sources.csv` | — | ✅ |
| 1 | Análisis exploratorio | Entender los documentos y sus problemas | `scripts/explorar_pdfs.py` | ✅ |
| 2 | Extracción y limpieza | PDF → texto limpio, división en artículos y consolidación de las modificaciones de 2014 y 2015 | `src/ingest.py`, `src/articulos.py`, `src/consolidar.py` | ✅ |
| 3 | Troceado (*chunking*) | Un chunk por artículo; los de más de 300 palabras se dividen por apartados. Cada chunk lleva un encabezado de contexto y metadatos para citar | `src/chunks.py` | ✅ |
| 4 | Conjunto de evaluación | 62 preguntas de 6 tipos (directas, parafraseadas, cifras, varios artículos, ambiguas y sin respuesta) con su respuesta y sus artículos | `eval/questions.json`, `scripts/validar_preguntas.py`, `scripts/revisar_preguntas.py` | ✅ |
| 5 | Indexación | Embedding de cada chunk con `BAAI/bge-m3` (1024 dimensiones), guardado en Chroma con sus metadatos | `src/index.py` | ✅ |
| 6 | Recuperación | Buscar los k chunks más parecidos a una pregunta y medir si aciertan (Acierto@k, Recall@k, MRR) | `src/retrieve.py`, `src/evaluate.py` | ✅ |
| 7 | Generación | Prompt + LLM (Gemini, nivel gratuito) → respuesta con citas, o "no lo encuentro" si no está en los documentos | `src/generate.py` | ⏳ |
| 8 | Mejoras y experimentos | Búsqueda híbrida, *reranker*, comparar troceados y modelos de embeddings | — | |
| 9 | Interfaz y despliegue | App en Streamlit publicada en Hugging Face Spaces | `app.py` | |
| 10 | Documentación final | Resultados, gráficas y lecciones aprendidas | `README.md` | |

## Resultados

Recuperación con `BAAI/bge-m3` sobre las 57 preguntas de evaluación con respuesta
(línea base, sin mejoras; detalle en [`eval/resultados/`](eval/resultados/)):

| Acierto@1 | Acierto@3 | Acierto@5 | Recall@5 | MRR |
|---|---|---|---|---|
| 72 % | 86 % | 91 % | 72 % | 0,79 |

*Acierto@k*: hay al menos un artículo correcto entre los k primeros resultados.
*Recall@k*: fracción de los artículos correctos que aparecen entre los k primeros.
*MRR*: media de 1 / posición del primer artículo correcto.

Punto débil: en las preguntas que responden a la vez el reglamento marco de la UCA y el
de la Escuela, casi nunca llegan los dos (Recall@5 del 37 %), porque el marco no usa la
sigla "TFG" y los alumnos sí. El análisis está en el [diario](docs/diario.md).

## Datos

Los documentos son normativa pública de la Universidad de Cádiz y de la Escuela Superior de
Ingeniería. No se incluyen en el repositorio: [`data/sources.csv`](data/sources.csv) recoge
el título, el organismo, la fecha y la URL oficial de cada uno. Se guardan en `data/raw/`.

## Estructura del código

`src/` contiene el *pipeline* (cada script lee la salida del anterior); `scripts/`, las
herramientas de análisis y comprobación.

```
data/raw/*.pdf
  │ src/ingest.py        texto limpio de cada PDF             → data/processed/<id>.txt
  │ src/articulos.py     división en artículos y disposiciones → data/processed/articulos/
  │ src/consolidar.py    aplica data/parches.json (2014, 2015)  → data/processed/consolidado/
  │ src/chunks.py        chunks con encabezado de contexto     → data/processed/chunks.json
  │ src/index.py         embeddings (bge-m3) en Chroma          → data/index/
  ▼
src/retrieve.py          pregunta → los k chunks más parecidos
src/generate.py          pregunta → chunks → LLM → respuesta con citas
src/evaluate.py          métricas de recuperación con eval/questions.json → eval/resultados/
src/evaluate_generation.py  calidad de las respuestas (código + LLM como juez) → eval/resultados/
```

| Script | Qué hace |
|---|---|
| `scripts/explorar_pdfs.py` | Análisis exploratorio: caracteres por página, tablas, encabezados repetidos, caracteres raros |
| `scripts/validar_extraccion.py` | Comprueba palabra a palabra que la extracción no inventa ni pierde texto |
| `scripts/borrador_parches.py` | Borrador de los parches de una modificación nueva, para revisarlo a mano |
| `scripts/validar_preguntas.py` | Comprueba el formato y las fuentes del conjunto de evaluación |
| `scripts/revisar_preguntas.py` | Muestra cada pregunta junto al texto de sus fuentes, para revisarla |

## Uso

Con el entorno virtual activado:

```bash
pip install -r requirements.txt
python scripts/explorar_pdfs.py        # análisis exploratorio de los PDFs
python src/ingest.py                   # extrae y limpia el texto -> data/processed/
python scripts/validar_extraccion.py   # comprueba que no se pierde ni se inventa texto
python src/articulos.py                # divide cada reglamento en artículos -> data/processed/articulos/
python src/consolidar.py               # aplica data/parches.json -> data/processed/consolidado/ (versión vigente)
python src/chunks.py                   # trocea la versión vigente -> data/processed/chunks.json
python scripts/validar_preguntas.py    # comprueba el conjunto de evaluación (eval/questions.json)
python scripts/revisar_preguntas.py    # muestra cada pregunta con el texto de sus fuentes, para revisarla
python src/index.py                    # embeddings de los chunks -> base vectorial en data/index/ (descarga el modelo la primera vez)
python src/retrieve.py "¿Las prácticas se cobran?"   # busca los chunks más parecidos a una pregunta
python src/evaluate.py                 # mide el buscador con eval/questions.json -> eval/resultados/
python src/generate.py "¿Las prácticas se cobran?"   # respuesta con citas (necesita GEMINI_API_KEY en .env)
python src/evaluate_generation.py      # evalúa las respuestas con un LLM como juez -> eval/resultados/
python src/evaluate_generation.py --calibracion   # muestra para corregir a mano -> eval/calibracion.csv
python src/evaluate_generation.py --acuerdo       # acuerdo entre el juez y la corrección humana

# Solo si se añade una modificación nueva de la normativa:
python scripts/borrador_parches.py     # borrador de los parches (revisarlo y pasarlo a data/parches.json)
```

## Licencia

El código se distribuye bajo licencia [MIT](LICENSE). El proyecto usa
[PyMuPDF](https://pymupdf.readthedocs.io/), distribuido bajo AGPL-3.0.
