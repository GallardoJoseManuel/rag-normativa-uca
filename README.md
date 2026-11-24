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
| 2 | Extracción y limpieza | PDF → texto limpio: quitar membretes, caracteres raros y páginas inútiles; aplicar las modificaciones | `src/ingest.py` | ⏳ |
| 3 | Troceado (*chunking*) | Dividir el texto en fragmentos (por artículo) con metadatos: documento, artículo, página | `src/ingest.py` | |
| 4 | Conjunto de evaluación | 40-60 preguntas escritas a mano con su respuesta y el artículo correcto | `eval/questions.json` | |
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
python scripts/explorar_pdfs.py   # análisis exploratorio de los PDFs
```

## Licencia

El código se distribuye bajo licencia [MIT](LICENSE). El proyecto usa
[PyMuPDF](https://pymupdf.readthedocs.io/), distribuido bajo AGPL-3.0.
