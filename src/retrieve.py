"""Paso 6: busca los chunks más parecidos a una pregunta.

La pregunta no se trocea: entera se convierte en un vector con el MISMO modelo que indexó
la colección (se lee de los metadatos de la colección, para no mezclar "mapas"), y Chroma
devuelve los k chunks cuyos vectores están más cerca (similitud coseno).

Lo usan evaluate.py (paso 6), la generación de respuestas (paso 7) y la app (paso 9).

Uso (desde la raíz del proyecto, después de index.py):
    python src/retrieve.py "¿Las prácticas se cobran?"
    python src/retrieve.py "¿Quién forma el tribunal?" -k 3 --documento tfgm_esi
"""
import argparse
import re
import sys

import chromadb
from sentence_transformers import SentenceTransformer

from index import INDICE, MODELO, PREFIJOS, nombre_coleccion

SUFIJO_PARTE = re.compile(r"_p\d+$")


def unidad(id_chunk: str) -> str:
    """Id del artículo o disposición al que pertenece un chunk: quita el sufijo _p1, _p2..."""
    return SUFIJO_PARTE.sub("", id_chunk)


class Buscador:
    """Abre la colección de un modelo y carga ese modelo una sola vez.

    Es una clase (y no una función suelta) porque cargar el modelo tarda unos segundos:
    se hace al crear el buscador y después cada búsqueda solo calcula un embedding.
    """

    def __init__(self, modelo: str = MODELO):
        cliente = chromadb.PersistentClient(path=str(INDICE))
        self.coleccion = cliente.get_collection(nombre_coleccion(modelo))
        # El modelo que indexó la colección es el que hay que usar con las preguntas.
        self.nombre_modelo = self.coleccion.metadata["modelo"]
        self.modelo = SentenceTransformer(self.nombre_modelo)
        self.prefijo = PREFIJOS.get(self.nombre_modelo, ("", ""))[1]

    def buscar(self, pregunta: str, k: int = 5, filtro: dict | None = None) -> list[dict]:
        """Devuelve los k chunks más parecidos a la pregunta, del más al menos parecido.

        filtro: condición sobre los metadatos, por ejemplo {"documento": "tfgm_esi"}.
        Cada resultado tiene id, unidad, similitud, texto y los metadatos del chunk.
        """
        vector = self.modelo.encode([self.prefijo + pregunta], normalize_embeddings=True)
        r = self.coleccion.query(query_embeddings=vector.tolist(), n_results=k, where=filtro,
                                 include=["documents", "metadatas", "distances"])
        # query admite varias preguntas a la vez y devuelve una lista por pregunta: [0]
        return [{"id": id_, "unidad": unidad(id_), "similitud": 1 - distancia,
                 "texto": texto, **metadatos}
                for id_, distancia, texto, metadatos in
                zip(r["ids"][0], r["distances"][0], r["documents"][0], r["metadatas"][0])]


def cita(resultado: dict) -> str:
    """Referencia legible de un chunk: 'Art. 22 (apartados 7-14) · practicas_uca_2012'."""
    if resultado["tipo"] == "articulo":
        texto = f"Art. {resultado['numero']}"
    else:
        texto = resultado["titulo"].capitalize()
    if resultado["apartados"]:
        plural = "s" if "-" in resultado["apartados"] else ""
        texto += f" (apartado{plural} {resultado['apartados']})"
    return f"{texto} · {resultado['documento']}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    parser = argparse.ArgumentParser(description="Busca los chunks más parecidos a una pregunta.")
    parser.add_argument("pregunta")
    parser.add_argument("-k", type=int, default=5, help="número de resultados (por defecto 5)")
    parser.add_argument("--documento", help="buscar solo en este reglamento (id de sources.csv)")
    parser.add_argument("--modelo", default=MODELO, help=f"colección a usar (por defecto {MODELO})")
    args = parser.parse_args()

    buscador = Buscador(args.modelo)
    filtro = {"documento": args.documento} if args.documento else None
    for i, r in enumerate(buscador.buscar(args.pregunta, args.k, filtro), start=1):
        print(f"\n{i}. [{r['similitud']:.3f}] {cita(r)} · {r['titulo']}")
        print("   " + r["texto"][:300].replace("\n", "\n   ") + ("..." if len(r["texto"]) > 300 else ""))


if __name__ == "__main__":
    main()
