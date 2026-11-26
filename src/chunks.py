"""Paso 3: trocea los reglamentos consolidados en chunks para el buscador.

Lee la versión vigente de cada reglamento (data/processed/consolidado/<id>.json,
generada por src/consolidar.py) y la divide en chunks:

- Un artículo o disposición de hasta MAX_PALABRAS palabras es un solo chunk.
- Uno más largo se divide por sus apartados de primer nivel (los "1.", "2."... o los
  "a)", "b)"..., según con cuál empiece). Cada apartado se lleva consigo sus
  subapartados y los párrafos que lo continúan, y se agrupan apartados seguidos hasta
  rondar MAX_PALABRAS. Si el artículo tiene una frase introductoria antes del primer
  apartado ("La entidad colaboradora está obligada a:"), se repite en cada trozo para
  que se entienda por sí solo.

Cada chunk guarda dos textos: "texto" (el de la norma, para mostrarlo y citarlo) y
"texto_embedding" (el mismo con un encabezado de contexto delante: documento >
sección > artículo y título). El segundo es el que se convertirá en embedding.

Al terminar comprueba que, quitando las introducciones repetidas, los chunks de cada
unidad reproducen su texto exacto, y se detiene con código de salida 1 si no.

Uso (desde la raíz del proyecto, después de consolidar.py):
    python src/chunks.py
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SOURCES = RAIZ / "data" / "sources.csv"
CONSOLIDADO = RAIZ / "data" / "processed" / "consolidado"
SALIDA = RAIZ / "data" / "processed" / "chunks.json"

MAX_PALABRAS = 300  # ~400-450 tokens en español: cabe en modelos con límite de 512

# Paso 8, experimento A: texto que se añade al título del documento SOLO en el encabezado del
# embedding (no en el texto que se muestra ni en las citas). El reglamento marco nunca usa la
# sigla "TFG", que es como preguntan los alumnos, y el buscador ponía casi toda la ESI por
# delante de cualquier artículo del marco.
CONTEXTO_DOCUMENTO = {
    "tfg_uca_2012": "TFG/TFM: Trabajo Fin de Grado y Trabajo Fin de Máster",
}

# Marca al principio de un párrafo, con un grupo con nombre para cada tipo.
MARCA = re.compile(r"^(?:(?P<num>\d+)\.(?:\s|$)"     # 1.
                   r"|(?P<letra>[a-zñ])\)"           # a)
                   r"|(?P<romano>[ivx]+)\.(?:\s|$)"  # iii.
                   r"|(?P<vineta>•))")               # •


def contar(texto: str) -> int:
    return len(texto.split())


def marca(parrafo: str) -> tuple[str, str] | None:
    """Devuelve (tipo, valor) de la marca con que empieza el párrafo, o None."""
    m = MARCA.match(parrafo)
    if not m:
        return None
    tipo = m.lastgroup
    return tipo, m.group(tipo)


def bloques(texto: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Separa el texto en introducción y apartados de primer nivel.

    Devuelve (intro, apartados): intro es la lista de párrafos anteriores al primer
    apartado y cada apartado es (valor_de_la_marca, párrafos). El primer nivel es el
    tipo de marca del primer párrafo marcado; las marcas de otro tipo (subapartados) y
    los párrafos sin marca se quedan dentro del apartado en curso.
    """
    intro, apartados, nivel = [], [], None
    for parrafo in texto.split("\n"):
        m = marca(parrafo)
        if m and nivel is None:
            nivel = m[0]
        if m and m[0] == nivel:
            apartados.append((m[1], [parrafo]))
        elif apartados:
            apartados[-1][1].append(parrafo)
        else:
            intro.append(parrafo)
    return intro, apartados


def agrupar(apartados: list[tuple[str, list[str]]], max_palabras: int,
            palabras_intro: int) -> list[list[tuple[str, list[str]]]]:
    """Agrupa apartados seguidos en grupos de tamaño parecido y de hasta max_palabras.

    Primero calcula cuántos grupos hacen falta y su tamaño objetivo (el total repartido
    a partes iguales), para no dejar un último trozo diminuto. Un apartado que por sí
    solo supera el máximo forma su propio grupo (no se parte un apartado por la mitad).
    """
    tamanos = [contar("\n".join(p)) for _, p in apartados]
    disponible = max_palabras - palabras_intro
    n_grupos = math.ceil(sum(tamanos) / disponible)
    objetivo = sum(tamanos) / n_grupos

    grupos, actual, palabras = [], [], 0
    for apartado, tamano in zip(apartados, tamanos):
        if actual and (palabras + tamano > disponible or palabras >= objetivo):
            grupos.append(actual)
            actual, palabras = [], 0
        actual.append(apartado)
        palabras += tamano
    grupos.append(actual)
    return grupos


def rango(marcas: list[str]) -> str:
    """["1", "2", "3"] -> "1-3"; ["a", "c"] -> "a)-c)"; ["b"] -> "b)"."""
    fmt = (lambda m: m) if marcas[0].isdigit() else (lambda m: f"{m})")
    if len(marcas) == 1:
        return fmt(marcas[0])
    return f"{fmt(marcas[0])}-{fmt(marcas[-1])}"


def encabezado(unidad: dict, titulo_documento: str, apartados: list[str]) -> str:
    """Contexto que se antepone al texto: documento > sección > artículo."""
    if unidad["tipo"] == "articulo":
        articulo = f"Art. {unidad['numero']}"
        if unidad["titulo"]:
            articulo += f". {unidad['titulo']}"
    else:
        articulo = unidad["titulo"]
    if apartados:
        articulo += f" (apartados {rango(apartados)})"
    if unidad["documento"] in CONTEXTO_DOCUMENTO:
        titulo_documento += f" ({CONTEXTO_DOCUMENTO[unidad['documento']]})"
    partes = [titulo_documento, unidad["seccion"], articulo]
    return " > ".join(p for p in partes if p)


def trocear(unidad: dict, fuente: dict, max_palabras: int = MAX_PALABRAS) -> list[dict]:
    """Devuelve los chunks de una unidad (artículo o disposición)."""
    base = {"documento": unidad["documento"], "titulo_documento": fuente["titulo"],
            "url": fuente["url"], "tipo": unidad["tipo"], "numero": unidad["numero"],
            "titulo": unidad["titulo"], "seccion": unidad["seccion"],
            "modificado_por": unidad["modificado_por"]}

    intro, apartados = bloques(unidad["texto"])
    if contar(unidad["texto"]) <= max_palabras or len(apartados) < 2:
        grupos = [None]  # un solo chunk con el texto completo
    else:
        grupos = agrupar(apartados, max_palabras, contar("\n".join(intro)))

    chunks = []
    for parte, grupo in enumerate(grupos, start=1):
        if grupo is None:
            texto, marcas = unidad["texto"], []
        else:
            texto = "\n".join(intro + [p for _, parrafos in grupo for p in parrafos])
            marcas = [m for m, _ in grupo]
        sufijo = f"_p{parte}" if len(grupos) > 1 else ""
        chunks.append({"id": unidad["id"] + sufijo, **base,
                       "apartados": rango(marcas) if marcas else "",
                       "parte": parte, "partes": len(grupos),
                       "texto": texto,
                       "texto_embedding": encabezado(unidad, fuente["titulo"], marcas) + "\n" + texto})
    return chunks


def comprobar(unidad: dict, chunks: list[dict]) -> list[str]:
    """Errores si los chunks no reproducen exactamente el texto de la unidad."""
    errores = []
    intro, _ = bloques(unidad["texto"])
    if len(chunks) == 1:
        reconstruido = chunks[0]["texto"]
    else:
        reconstruido = "\n".join(intro + [p for c in chunks
                                          for p in c["texto"].split("\n")[len(intro):]])
    if reconstruido != unidad["texto"]:
        errores.append(f"{unidad['id']}: los chunks no reproducen el texto original")
    for c in chunks:
        if intro and c["partes"] > 1 and c["texto"].split("\n")[:len(intro)] != intro:
            errores.append(f"{c['id']}: no empieza por la introducción del artículo")
    return errores


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    with open(SOURCES, encoding="utf-8", newline="") as f:
        fuentes = {r["id"]: r for r in csv.DictReader(f) if r["tipo"] == "reglamento"}

    todos, errores = [], []
    for documento, fuente in fuentes.items():
        unidades = json.loads((CONSOLIDADO / f"{documento}.json").read_text(encoding="utf-8"))
        chunks_doc = []
        for unidad in unidades:
            chunks = trocear(unidad, fuente)
            errores += comprobar(unidad, chunks)
            chunks_doc += chunks
        divididas = [u["id"] for u in unidades
                     if sum(c["id"].startswith(u["id"] + "_p") for c in chunks_doc)]
        print(f"✓ {documento}: {len(unidades)} unidades -> {len(chunks_doc)} chunks "
              f"({len(divididas)} unidades divididas)")
        todos += chunks_doc

    ids = [c["id"] for c in todos]
    if len(ids) != len(set(ids)):
        errores.append("hay ids de chunk repetidos")
    if errores:
        sys.exit("✗ " + "\n✗ ".join(errores))

    tamanos = sorted(contar(c["texto"]) for c in todos)
    largos = [c for c in todos if contar(c["texto"]) > MAX_PALABRAS]
    print(f"Total: {len(todos)} chunks; palabras por chunk: mínimo {tamanos[0]}, "
          f"mediana {tamanos[len(tamanos) // 2]}, máximo {tamanos[-1]}")
    for c in largos:
        print(f"  aviso: {c['id']} tiene {contar(c['texto'])} palabras "
              f"(un solo apartado más largo que {MAX_PALABRAS})")

    SALIDA.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
