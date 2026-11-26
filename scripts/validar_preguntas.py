"""Paso 4: comprueba el conjunto de evaluación (eval/questions.json).

Cada pregunta tiene: id, pregunta, respuesta (de referencia), fuentes (ids de las
unidades del consolidado donde está la respuesta; vacía si no está en los documentos)
y tipo.

Errores (código de salida 1): JSON mal formado, campos que faltan o vacíos, ids o
preguntas repetidos, un tipo desconocido, una fuente que no existe en
data/processed/consolidado/ o una pregunta "sin_respuesta" con fuentes (o al revés).

Además muestra cuántas preguntas hay por tipo y reglamento, qué parte del corpus
cubren y el solapamiento de vocabulario entre cada pregunta y sus fuentes: si una
pregunta repite las palabras del artículo, el buscador acierta "por coincidencia" y la
evaluación sale inflada. Avisa de las preguntas que no son "directa" y pasan del umbral.

Uso (desde la raíz del proyecto, después de consolidar.py):
    python scripts/validar_preguntas.py
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = RAIZ / "eval" / "questions.json"
CONSOLIDADO = RAIZ / "data" / "processed" / "consolidado"

CAMPOS = ["id", "pregunta", "respuesta", "fuentes", "tipo"]
TIPOS = {"directa", "parafrase", "cifra", "multi", "ambigua", "sin_respuesta"}
ID = re.compile(r"^q\d{3}$")
UMBRAL_SOLAPAMIENTO = 0.6

# Palabras muy frecuentes que no dicen nada del tema (sin tildes: se comparan normalizadas).
VACIAS = set("""el la los las un una unos unas de del al a en y o u e que se su sus por para
con sin como cual cuales cuando donde quien quienes es son ser hay me mi mis te tu yo
lo le les no si ya mas pero este esta estos estas ese esa eso puede pueden puedo
tengo tiene tienen hace hacer debo debe deben cuanto cuanta cuantos cuantas
que algun alguna hasta tras sobre entre""".split())


def normalizar(texto: str) -> list[str]:
    """Palabras en minúscula, sin tildes y sin palabras vacías."""
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return [p for p in re.findall(r"\w+", sin_tildes) if p not in VACIAS and len(p) > 2]


def solapamiento(pregunta: str, textos: list[str]) -> float:
    """Fracción de las palabras de la pregunta que aparecen en sus fuentes."""
    palabras = set(normalizar(pregunta))
    if not palabras:
        return 0.0
    fuente = set(p for t in textos for p in normalizar(t))
    return len(palabras & fuente) / len(palabras)


def cargar_unidades() -> dict[str, dict]:
    unidades = {}
    for ruta in sorted(CONSOLIDADO.glob("*.json")):
        for u in json.loads(ruta.read_text(encoding="utf-8")):
            unidades[u["id"]] = u
    return unidades


def comprobar(preguntas: list, unidades: dict[str, dict]) -> list[str]:
    errores = []
    if not isinstance(preguntas, list):
        return ["el archivo tiene que ser una lista de preguntas"]
    for i, q in enumerate(preguntas):
        nombre = q.get("id", f"pregunta n.º {i + 1}")
        faltan = [c for c in CAMPOS if c not in q]
        if faltan:
            errores.append(f"{nombre}: faltan los campos {faltan}")
            continue
        if not ID.match(q["id"]):
            errores.append(f"{nombre}: el id tiene que ser como q001")
        for campo in ("pregunta", "respuesta"):
            if not str(q[campo]).strip():
                errores.append(f"{nombre}: '{campo}' está vacío")
        if q["tipo"] not in TIPOS:
            errores.append(f"{nombre}: tipo desconocido '{q['tipo']}' (válidos: {sorted(TIPOS)})")
        if not isinstance(q["fuentes"], list):
            errores.append(f"{nombre}: 'fuentes' tiene que ser una lista")
            continue
        for fuente in q["fuentes"]:
            if fuente not in unidades:
                errores.append(f"{nombre}: la fuente '{fuente}' no existe en el consolidado")
        if len(set(q["fuentes"])) != len(q["fuentes"]):
            errores.append(f"{nombre}: hay fuentes repetidas")
        if (q["tipo"] == "sin_respuesta") != (not q["fuentes"]):
            errores.append(f"{nombre}: las preguntas 'sin_respuesta' (y solo ellas) van sin fuentes")
        if q["tipo"] == "multi" and len(q["fuentes"]) < 2:
            errores.append(f"{nombre}: una pregunta 'multi' necesita al menos 2 fuentes")

    for campo in ("id", "pregunta"):
        repetidos = [v for v, n in Counter(str(q.get(campo, "")).strip().lower()
                                           for q in preguntas).items() if n > 1]
        if repetidos:
            errores.append(f"{campo} repetido: {repetidos}")
    return errores


def resumen(preguntas: list, unidades: dict[str, dict]) -> None:
    print(f"✓ {len(preguntas)} preguntas sin errores\n")
    por_tipo = Counter(q["tipo"] for q in preguntas)
    print("Por tipo:   " + ", ".join(f"{t} {por_tipo[t]}" for t in sorted(TIPOS)))
    por_doc = Counter(unidades[f]["documento"] for q in preguntas for f in set(q["fuentes"]))
    print("Por reglamento (preguntas que lo citan): "
          + ", ".join(f"{d} {n}" for d, n in sorted(por_doc.items())))

    citadas = {f for q in preguntas for f in q["fuentes"]}
    print(f"Cobertura: {len(citadas)} de {len(unidades)} artículos y disposiciones "
          f"aparecen como fuente\n")

    print(f"Solapamiento de vocabulario pregunta-fuentes (media por tipo):")
    valores = {}
    for q in preguntas:
        if q["fuentes"]:
            valores[q["id"]] = solapamiento(q["pregunta"], [unidades[f]["texto"] for f in q["fuentes"]])
    for tipo in sorted(TIPOS - {"sin_respuesta"}):
        de_tipo = [valores[q["id"]] for q in preguntas if q["tipo"] == tipo and q["id"] in valores]
        if de_tipo:
            print(f"  {tipo:<10} {sum(de_tipo) / len(de_tipo):.2f}")
    altos = [q for q in preguntas if q["tipo"] != "directa"
             and valores.get(q["id"], 0) > UMBRAL_SOLAPAMIENTO]
    for q in altos:
        print(f"  aviso: {q['id']} ({q['tipo']}) repite el {valores[q['id']]:.0%} de su "
              f"vocabulario de las fuentes: {q['pregunta']}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    try:
        preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"✗ No existe {PREGUNTAS.relative_to(RAIZ)}")
    except json.JSONDecodeError as error:
        sys.exit(f"✗ {PREGUNTAS.relative_to(RAIZ)} no es JSON válido: {error}")

    unidades = cargar_unidades()
    errores = comprobar(preguntas, unidades)
    if errores:
        sys.exit("✗ " + "\n✗ ".join(errores))
    resumen(preguntas, unidades)


if __name__ == "__main__":
    main()
