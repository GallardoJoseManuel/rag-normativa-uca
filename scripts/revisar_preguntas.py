"""Paso 4: muestra cada pregunta de evaluación junto al texto de sus fuentes.

Sirve para revisar a mano que la respuesta de referencia dice lo que dicen los
artículos y que las fuentes son las correctas (ni sobran ni faltan). No comprueba nada
automáticamente: para eso está validar_preguntas.py.

Uso (desde la raíz del proyecto):
    python scripts/revisar_preguntas.py                 # todas
    python scripts/revisar_preguntas.py q053 q062       # solo esas
    python scripts/revisar_preguntas.py --tipo ambigua  # solo un tipo
    python scripts/revisar_preguntas.py --salida revision.md   # a un archivo (UTF-8)
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = RAIZ / "eval" / "questions.json"
CONSOLIDADO = RAIZ / "data" / "processed" / "consolidado"


def cargar_unidades() -> dict[str, dict]:
    unidades = {}
    for ruta in sorted(CONSOLIDADO.glob("*.json")):
        for u in json.loads(ruta.read_text(encoding="utf-8")):
            unidades[u["id"]] = u
    return unidades


def formatear(q: dict, unidades: dict[str, dict]) -> str:
    """Una pregunta en Markdown: pregunta, respuesta y el texto de cada fuente."""
    lineas = [f"## {q['id']} ({q['tipo']}): {q['pregunta']}", "",
              f"**Respuesta de referencia:** {q['respuesta']}", ""]
    if not q["fuentes"]:
        lineas += ["_Sin fuentes: la respuesta no debería estar en los documentos._", ""]
    for fuente in q["fuentes"]:
        u = unidades.get(fuente)
        if u is None:
            lineas += [f"### {fuente}: NO EXISTE EN EL CONSOLIDADO", ""]
            continue
        lineas += [f"### {fuente}: {u['titulo']}", ""]
        lineas += [f"> {parrafo}" for parrafo in u["texto"].split("\n")]
        lineas.append("")
    return "\n".join(lineas)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    parser = argparse.ArgumentParser(description="Muestra cada pregunta con el texto de sus fuentes.")
    parser.add_argument("ids", nargs="*", help="ids de las preguntas (por defecto, todas)")
    parser.add_argument("--tipo", help="mostrar solo las preguntas de este tipo")
    parser.add_argument("--salida", help="escribir en este archivo en vez de en la consola")
    args = parser.parse_args()

    preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
    if args.ids:
        desconocidos = set(args.ids) - {q["id"] for q in preguntas}
        if desconocidos:
            sys.exit(f"✗ No existen estas preguntas: {sorted(desconocidos)}")
        preguntas = [q for q in preguntas if q["id"] in args.ids]
    if args.tipo:
        preguntas = [q for q in preguntas if q["tipo"] == args.tipo]

    unidades = cargar_unidades()
    texto = "\n---\n\n".join(formatear(q, unidades) for q in preguntas)
    if args.salida:
        Path(args.salida).write_text(texto, encoding="utf-8")
        print(f"✓ {len(preguntas)} preguntas -> {args.salida}")
    else:
        print(texto)


if __name__ == "__main__":
    main()
