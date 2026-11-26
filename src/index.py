"""Paso 5: calcula el embedding de cada chunk y lo guarda en una base vectorial (Chroma).

Lee data/processed/chunks.json (generado por src/chunks.py), convierte el campo
"texto_embedding" de cada chunk en un vector con el modelo de embeddings y guarda en una
colección de Chroma, en data/index/, el id, el vector, el texto de la norma y los
metadatos de cada chunk.

- Los embeddings se calculan aquí con sentence-transformers y se le pasan a Chroma ya
  hechos, para controlar exactamente qué modelo se usa.
- Los vectores se normalizan (longitud 1) y la colección usa la distancia coseno.
- Hay una colección por modelo (normativa_<modelo>), para poder comparar modelos sin
  reindexar. Cada ejecución borra y recrea la colección del modelo: así nunca quedan
  restos de una indexación anterior.

Al terminar comprueba que la colección tiene exactamente los ids de chunks.json y que
ningún chunk supera el límite de tokens del modelo (se cortaría sin avisar). Si algo
falla, se detiene con código de salida 1.

Uso (desde la raíz del proyecto, después de chunks.py):
    python src/index.py                          # modelo por defecto (BAAI/bge-m3)
    python src/index.py --modelo intfloat/multilingual-e5-small
"""
import argparse
import json
import sys
from pathlib import Path

import chromadb # Base vectorial
from sentence_transformers import SentenceTransformer   # Modelo de embeddings que calcula los vectores

RAIZ = Path(__file__).resolve().parent.parent
CHUNKS = RAIZ / "data" / "processed" / "chunks.json"
INDICE = RAIZ / "data" / "index"

MODELO = "BAAI/bge-m3"
# Algunos modelos (los e5) se entrenaron con un prefijo delante de cada pasaje y de cada
# pregunta; sin él dan peores resultados sin avisar. bge-m3 no lo necesita.
PREFIJOS = {"intfloat/multilingual-e5-small": ("passage: ", "query: "),
            "intfloat/multilingual-e5-base": ("passage: ", "query: "),
            "intfloat/multilingual-e5-large": ("passage: ", "query: ")}


def nombre_coleccion(modelo: str) -> str:
    """"BAAI/bge-m3" -> "normativa_bge-m3"."""
    return "normativa_" + modelo.split("/")[-1].lower()


def metadatos(chunk: dict) -> dict:
    """Metadatos para Chroma, que solo admite valores simples (texto, número, booleano)."""
    datos = {campo: chunk[campo] for campo in
             ("documento", "titulo_documento", "url", "tipo", "titulo", "seccion",
              "apartados", "parte", "partes")}
    datos["modificado_por"] = ", ".join(chunk["modificado_por"])  # lista -> texto
    if chunk["numero"] is not None:  # las disposiciones no tienen número
        datos["numero"] = chunk["numero"]
    return datos


def contar_tokens(modelo: SentenceTransformer, textos: list[str]) -> list[int]:
    """Tokens de cada texto según el tokenizador del modelo (sin cortar)."""
    return [len(ids) for ids in modelo.tokenizer(textos, truncation=False)["input_ids"]]


def indexar(chunks: list[dict], nombre_modelo: str) -> chromadb.Collection:
    """Calcula los embeddings y crea (o recrea) la colección del modelo."""
    prefijo = PREFIJOS.get(nombre_modelo, ("", ""))[0]
    textos = [prefijo + c["texto_embedding"] for c in chunks]

    print(f"Cargando el modelo {nombre_modelo}...")
    modelo = SentenceTransformer(nombre_modelo)

    tokens = contar_tokens(modelo, textos)
    limite = modelo.max_seq_length
    print(f"Tokens por chunk: máximo {max(tokens)} (límite del modelo: {limite})")
    cortados = [(c["id"], n) for c, n in zip(chunks, tokens) if n > limite]
    if cortados:
        sys.exit(f"✗ {len(cortados)} chunks superan el límite y se cortarían: {cortados}")

    print(f"Calculando {len(textos)} embeddings...")
    
    # Vectores = matriz numpy de chunks x dimensiones, normalizados (longitud 1) para usar distancia coseno
    vectores = modelo.encode(textos, normalize_embeddings=True, batch_size=8,
                             show_progress_bar=True)


    cliente = chromadb.PersistentClient(path=str(INDICE))
    nombre = nombre_coleccion(nombre_modelo)
    if nombre in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(nombre)
    coleccion = cliente.create_collection(
        nombre,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"modelo": nombre_modelo, "dimensiones": int(vectores.shape[1])})
    coleccion.add(ids=[c["id"] for c in chunks],
                  embeddings=vectores.tolist(),
                  documents=[c["texto"] for c in chunks],
                  metadatas=[metadatos(c) for c in chunks])
    return coleccion


def comprobar(coleccion: chromadb.Collection, chunks: list[dict]) -> list[str]:
    """Errores si la colección no tiene exactamente los chunks de chunks.json."""
    errores = []
    esperados = {c["id"] for c in chunks}
    guardados = set(coleccion.get(include=[])["ids"])
    if len(esperados) != len(chunks):
        errores.append("chunks.json tiene ids repetidos")
    if guardados != esperados:
        errores.append(f"faltan {sorted(esperados - guardados)} y sobran {sorted(guardados - esperados)}")
    return errores


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    parser = argparse.ArgumentParser(description="Indexa los chunks en Chroma.")
    parser.add_argument("--modelo", default=MODELO, help=f"modelo de embeddings (por defecto {MODELO})")
    args = parser.parse_args()

    chunks = json.loads(CHUNKS.read_text(encoding="utf-8"))
    coleccion = indexar(chunks, args.modelo)
    errores = comprobar(coleccion, chunks)
    if errores:
        sys.exit("✗ " + "\n✗ ".join(errores))
    print(f"✓ {coleccion.count()} chunks en la colección '{coleccion.name}' "
          f"({coleccion.metadata['dimensiones']} dimensiones) -> {INDICE.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
