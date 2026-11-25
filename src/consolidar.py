"""Paso 2 (final): aplica los parches y genera los reglamentos consolidados.

Lee los artículos originales de cada reglamento (data/processed/articulos/<id>.json,
generados por src/articulos.py) y los parches revisados (data/parches.json), aplica
los parches en el orden en que aparecen y guarda la versión vigente en
data/processed/consolidado/<id>.json. Esta es la versión que irá al RAG.

Cada unidad consolidada tiene: id, documento, tipo, numero, titulo, seccion, texto y
modificado_por (lista de modificaciones que la han cambiado; vacía si ninguna).

El script es estricto: se detiene con un error (código de salida 1) si un parche no
está revisado, si su texto antiguo no aparece exactamente una vez en el artículo, si
el artículo no existe o si al terminar los artículos no van del 1 al N sin huecos.
Así es imposible aplicar un cambio en el sitio equivocado sin enterarse.

Uso (desde la raíz del proyecto, después de ingest.py y articulos.py):
    python src/consolidar.py
"""
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SOURCES = RAIZ / "data" / "sources.csv"
PARCHES = RAIZ / "data" / "parches.json"
ARTICULOS = RAIZ / "data" / "processed" / "articulos"
SALIDA = RAIZ / "data" / "processed" / "consolidado"

CAMPOS = ["id", "documento", "tipo", "numero", "titulo", "seccion", "texto", "modificado_por"]


class ErrorParche(Exception):
    """Un parche no se puede aplicar. El mensaje explica cuál y por qué."""


def describir(parche: dict) -> str:
    return f"{parche['fuente']} ({parche['cambio']}, {parche['operacion']}, art. " \
           f"{parche.get('articulo', parche.get('articulos'))})"


def buscar_articulo(unidades: list[dict], numero: int, parche: dict) -> dict:
    """Devuelve el artículo con ese número, o falla si no existe o hay más de uno."""
    encontrados = [u for u in unidades if u["tipo"] == "articulo" and u["numero"] == numero]
    if len(encontrados) != 1:
        raise ErrorParche(f"{describir(parche)}: hay {len(encontrados)} artículos con el número {numero}")
    return encontrados[0]


def marcar(unidad: dict, parche: dict) -> None:
    """Anota en la unidad qué modificación la ha cambiado (sin repetir)."""
    if parche["fuente"] not in unidad["modificado_por"]:
        unidad["modificado_por"].append(parche["fuente"])


def aplicar(unidades: list[dict], parche: dict) -> None:
    """Aplica un parche sobre la lista de unidades de un reglamento (la modifica en el sitio)."""
    operacion = parche["operacion"]

    if operacion == "reemplazar_texto":
        articulo = buscar_articulo(unidades, parche["articulo"], parche)
        apariciones = articulo["texto"].count(parche["texto_antiguo"])
        if not parche["texto_antiguo"] or apariciones != 1:
            raise ErrorParche(f"{describir(parche)}: el texto antiguo aparece {apariciones} veces "
                              f"(tiene que aparecer exactamente 1)")
        articulo["texto"] = articulo["texto"].replace(parche["texto_antiguo"], parche["texto_nuevo"])
        marcar(articulo, parche)

    elif operacion == "reemplazar_articulo":
        articulo = buscar_articulo(unidades, parche["articulo"], parche)
        articulo["titulo"] = parche["titulo"]
        articulo["texto"] = parche["texto_nuevo"]
        marcar(articulo, parche)

    elif operacion == "renumerar":
        articulo = buscar_articulo(unidades, parche["articulo"], parche)
        articulo["numero"] = parche["nuevo_numero"]
        articulo["id"] = f"{articulo['documento']}_art_{parche['nuevo_numero']}"
        marcar(articulo, parche)

    elif operacion == "añadir_articulo":
        numero = parche["articulo"]
        if any(u["tipo"] == "articulo" and u["numero"] == numero for u in unidades):
            raise ErrorParche(f"{describir(parche)}: ya existe un artículo {numero} "
                              f"(¿falta renumerar antes?)")
        documento = parche["reglamento"]
        unidades.append({"id": f"{documento}_art_{numero}", "documento": documento,
                         "tipo": "articulo", "numero": numero, "titulo": parche["titulo"],
                         "seccion": "", "texto": parche["texto_nuevo"],
                         "modificado_por": [parche["fuente"]]})

    elif operacion == "asignar_seccion":
        for numero in parche["articulos"]:
            buscar_articulo(unidades, numero, parche)["seccion"] = parche["seccion"]
            # Cambiar solo la sección no cambia el contenido: no se marca como modificado.

    else:
        raise ErrorParche(f"{describir(parche)}: operación desconocida")


def ordenar(unidades: list[dict]) -> list[dict]:
    """Artículos por número y, después, las disposiciones en su orden original."""
    articulos = sorted((u for u in unidades if u["tipo"] == "articulo"), key=lambda u: u["numero"])
    disposiciones = [u for u in unidades if u["tipo"] != "articulo"]
    return articulos + disposiciones


def consolidar(reglamento: str, parches: list[dict]) -> list[dict]:
    """Devuelve las unidades consolidadas de un reglamento."""
    originales = json.loads((ARTICULOS / f"{reglamento}.json").read_text(encoding="utf-8"))
    # Copia de cada unidad solo con los campos de salida (sin "encabezado", que es el
    # texto del PDF y dejaría de cuadrar al renumerar).
    unidades = [{**{c: u.get(c) for c in CAMPOS if c != "modificado_por"}, "modificado_por": []}
                for u in originales]

    for parche in parches:
        if parche.get("revisado") is not True:
            raise ErrorParche(f"{describir(parche)}: no está revisado")
        aplicar(unidades, parche)

    unidades = ordenar(unidades)
    numeros = [u["numero"] for u in unidades if u["tipo"] == "articulo"]
    if numeros != list(range(1, len(numeros) + 1)):
        raise ErrorParche(f"{reglamento}: los artículos no van del 1 al N sin huecos: {numeros}")
    return [{c: u[c] for c in CAMPOS} for u in unidades]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    SALIDA.mkdir(parents=True, exist_ok=True)
    with open(SOURCES, encoding="utf-8", newline="") as f:
        reglamentos = [r["id"] for r in csv.DictReader(f) if r["tipo"] == "reglamento"]
    todos = json.loads(PARCHES.read_text(encoding="utf-8"))

    desconocidos = {p["reglamento"] for p in todos} - set(reglamentos)
    if desconocidos:
        sys.exit(f"✗ Hay parches para reglamentos que no están en sources.csv: {desconocidos}")

    try:
        for reglamento in reglamentos:
            parches = [p for p in todos if p["reglamento"] == reglamento]
            unidades = consolidar(reglamento, parches)
            ruta = SALIDA / f"{reglamento}.json"
            ruta.write_text(json.dumps(unidades, ensure_ascii=False, indent=2), encoding="utf-8")

            modificados = [u for u in unidades if u["modificado_por"]]
            n_art = sum(u["tipo"] == "articulo" for u in unidades)
            print(f"✓ {reglamento}: {len(parches)} parches aplicados -> {n_art} artículos, "
                  f"{len(unidades) - n_art} disposiciones -> {ruta.relative_to(RAIZ)}")
            if modificados:
                print(f"    modificados: {', '.join(str(u['numero']) for u in modificados)}")
    except ErrorParche as error:
        sys.exit(f"✗ {error}")


if __name__ == "__main__":
    main()
