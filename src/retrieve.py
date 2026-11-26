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

# Paso 8, experimento B: búsqueda diversificada por reglamento. El reglamento de la ESI usa
# la sigla "TFG" en todas partes y tapa al reglamento marco, aunque buscando solo dentro del
# marco su artículo correcto sale casi siempre el primero. Si entre los VENTANA primeros
# resultados hay alguno de la ESI (la pregunta es de TFG), se reservan RESERVA_MARCO de esos
# puestos para los mejores chunks del marco. 0 = desactivado (búsqueda normal).
DOCUMENTO_ESPECIFICO = "tfgm_esi"
DOCUMENTO_MARCO = "tfg_uca_2012"
RESERVA_MARCO = 0
VENTANA = 5  # los chunks que recibe el LLM


def unidad(id_chunk: str) -> str:
    """Id del artículo o disposición al que pertenece un chunk: quita el sufijo _p1, _p2..."""
    return SUFIJO_PARTE.sub("", id_chunk)


class Buscador:
    """Abre la colección de un modelo y carga ese modelo una sola vez.

    Es una clase (y no una función suelta) porque cargar el modelo tarda unos segundos:
    se hace al crear el buscador y después cada búsqueda solo calcula un embedding.
    """

    def __init__(self, modelo: str = MODELO, reserva_marco: int = RESERVA_MARCO):
        self.reserva_marco = reserva_marco
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
        Sin filtro y con reserva_marco > 0, aplica la búsqueda diversificada (diversificar).
        """
        vector = self.modelo.encode([self.prefijo + pregunta], normalize_embeddings=True).tolist()
        resultados = self._consultar(vector, k, filtro)
        if filtro is None and self.reserva_marco > 0:
            resultados = self.diversificar(vector, resultados, k)
        return resultados

    def diversificar(self, vector: list, resultados: list[dict], k: int) -> list[dict]:
        """Asegura RESERVA_MARCO chunks del marco entre los VENTANA primeros si la pregunta es de TFG.

        Los del marco que faltan sustituyen a los últimos puestos de la ventana; los que
        salen de la ventana bajan, en su orden, justo detrás. El 1.er resultado no cambia.
        """
        n = min(VENTANA, k)
        ventana = resultados[:n]
        if not any(r["documento"] == DOCUMENTO_ESPECIFICO for r in ventana):
            return resultados  # no es una pregunta de TFG
        faltan = self.reserva_marco - sum(r["documento"] == DOCUMENTO_MARCO for r in ventana)
        if faltan <= 0:
            return resultados  # el marco ya tiene sus puestos
        ids = {r["id"] for r in ventana}
        marco = [r for r in self._consultar(vector, n, {"documento": DOCUMENTO_MARCO})
                 if r["id"] not in ids][:faltan]
        nuevos = {r["id"] for r in marco}
        quedan = n - len(marco)
        resto = [r for r in resultados if r["id"] not in nuevos]
        return (resto[:quedan] + marco + resto[quedan:])[:k]

    def _consultar(self, vector: list, k: int, filtro: dict | None) -> list[dict]:
        r = self.coleccion.query(query_embeddings=vector, n_results=k, where=filtro,
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
    parser.add_argument("--reserva-marco", type=int, default=RESERVA_MARCO,
                        help=f"puestos reservados al reglamento marco en preguntas de TFG (por defecto {RESERVA_MARCO})")
    args = parser.parse_args()

    buscador = Buscador(args.modelo, args.reserva_marco)
    filtro = {"documento": args.documento} if args.documento else None
    for i, r in enumerate(buscador.buscar(args.pregunta, args.k, filtro), start=1):
        print(f"\n{i}. [{r['similitud']:.3f}] {cita(r)} · {r['titulo']}")
        print("   " + r["texto"][:300].replace("\n", "\n   ") + ("..." if len(r["texto"]) > 300 else ""))


if __name__ == "__main__":
    main()
