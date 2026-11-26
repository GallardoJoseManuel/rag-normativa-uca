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
| 5 | Indexación | Calcular el embedding de cada chunk y guardarlo en Chroma | `src/index.py` | |
| 6 | Recuperación | Devolver los k chunks más relevantes para una pregunta y medir si aciertan (Recall@k) | `src/retrieve.py`, `src/evaluate.py` | |
| 7 | Generación | Prompt + LLM → respuesta con citas, o "no lo sé" si no está en los documentos | `src/generate.py` | |
| 8 | Mejoras y experimentos | Búsqueda híbrida, *reranker*, comparar troceados y modelos de embeddings | — | |
| 9 | Interfaz y despliegue | App en Streamlit publicada en Hugging Face Spaces | `app.py` | |
| 10 | Documentación final | Resultados, gráficas y lecciones aprendidas | `README.md` | |

## Datos

Los documentos son normativa pública de la Universidad de Cádiz y de la Escuela Superior de
Ingeniería. No se incluyen en el repositorio: [`data/sources.csv`](data/sources.csv) recoge
el título, el organismo, la fecha y la URL oficial de cada uno. Se guardan en `data/raw/`.

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

# Solo si se añade una modificación nueva de la normativa:
python scripts/borrador_parches.py     # borrador de los parches (revisarlo y pasarlo a data/parches.json)
```

## Licencia

El código se distribuye bajo licencia [MIT](LICENSE). El proyecto usa
[PyMuPDF](https://pymupdf.readthedocs.io/), distribuido bajo AGPL-3.0.
