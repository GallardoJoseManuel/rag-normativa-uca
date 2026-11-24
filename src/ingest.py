"""Paso 2 del pipeline: extracción y limpieza del texto de los PDFs del corpus.

Para cada documento de data/sources.csv que tenga rango de páginas útil
(pagina_inicio, pagina_fin), extrae el texto de esas páginas, lo limpia y lo
guarda en data/processed/<id>.txt para poder revisarlo.

Limpieza aplicada (conclusiones del análisis exploratorio, docs/diario.md):
- Quita las líneas que se repiten en muchas páginas (membretes de la ESI y del
  Vicerrectorado), sin tocar las marcas de apartado como "a)" o "1.".
- Quita las líneas de número de página ("pág. 5").
- Quita los caracteres de control (p. ej. \\x03) y cambia los espacios no
  separables (\\xa0) por espacios normales.
- Une todas las páginas en un solo texto, para no cortar artículos que
  continúan en la página siguiente.

Uso (desde la raíz del proyecto, con el entorno activado):
    python src/ingest.py
"""
import collections  # Para Counter, que cuenta cuántas páginas tienen cada línea
import csv          
import math     
import re   
import sys  
from pathlib import Path

import pymupdf

RAIZ = Path(__file__).resolve().parent.parent
SOURCES = RAIZ / "data" / "sources.csv"
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"

# Caracteres de control, salvo el tabulador (\x09) y el salto de línea (\x0a).
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# Línea que solo contiene el número de página: "pág. 5", "Pág 12".
NUMERO_PAGINA = re.compile(r"^p[áa]g\.?\s*\d+$", re.IGNORECASE)
# Marcas de apartado que pueden repetirse en muchas páginas sin ser encabezados:
# "a)", "b)", "1.", "iii.", ...
MARCA_APARTADO = re.compile(r"^([a-z]|\d+|[ivx]+)[).]$", re.IGNORECASE)


def limpiar_linea(linea: str) -> str:
    """Quita caracteres de control, normaliza espacios y recorta la línea."""
    linea = CONTROL.sub("", linea)           # 1. borra los caracteres de control
    linea = linea.replace("\xa0", " ")       # 2. espacio no separable -> espacio normal
    linea = re.sub(r"[ \t]+", " ", linea)    # 3. varios espacios seguidos -> uno
    return linea.strip()                     # 4. quita espacios al principio y al final


def detectar_encabezados(doc: pymupdf.Document, fraccion: float = 0.5) -> set[str]:
    """Devuelve las líneas que aparecen en al menos `fraccion` de las páginas.

    Se calcula sobre el documento completo (no solo el rango útil) para tener
    más páginas en las que contar. Con menos de 3 páginas no hay forma fiable
    de distinguir un encabezado de una línea normal, así que no se detecta nada.
    """
    if len(doc) < 3:
        return set()

    paginas_por_linea = collections.Counter()   # cuenta cuántas páginas tienen cada línea
    for page in doc:
        lineas = {limpiar_linea(l) for l in page.get_text().splitlines()} # set: una vez por página
        paginas_por_linea.update(l for l in lineas if l)  # set: una vez por página

    umbral = max(3, math.ceil(len(doc) * fraccion))
    resultado = set()
    for linea, n in paginas_por_linea.items():
        if n >= umbral and not MARCA_APARTADO.match(linea):
            resultado.add(linea)
    return resultado


def extraer_texto(ruta_pdf, pagina_inicio: int, pagina_fin: int) -> str:
    """Devuelve el texto limpio de las páginas indicadas, unido en un solo string.

    Las páginas se numeran desde 1 y el rango incluye las dos páginas indicadas,
    igual que en data/sources.csv (PyMuPDF numera desde 0).
    Se conservan los saltos de línea y se deja una línea en blanco entre párrafos.
    """
    doc = pymupdf.open(ruta_pdf)
    if not 1 <= pagina_inicio <= pagina_fin <= len(doc):
        raise ValueError(
            f"{Path(ruta_pdf).name}: rango {pagina_inicio}-{pagina_fin} no válido "
            f"(el documento tiene {len(doc)} páginas)"
        )

    encabezados = detectar_encabezados(doc)
    paginas = []
    for num in range(pagina_inicio - 1, pagina_fin):  # de numeración 1.. a 0..
        lineas = []
        for linea in doc[num].get_text().splitlines():
            linea = limpiar_linea(linea)
            if linea in encabezados or NUMERO_PAGINA.match(linea):
                continue
            lineas.append(linea)  # las vacías se quedan: separan párrafos
        # Quitar las líneas vacías del principio y del final de la página, para
        # que el salto de página no parezca un cambio de párrafo.
        paginas.append("\n".join(lineas).strip("\n"))

    texto = "\n".join(paginas)
    texto = re.sub(r"\n{3,}", "\n\n", texto)  # como mucho una línea en blanco seguida
    return texto.strip() + "\n"


def leer_fuentes() -> list[dict]:
    """Lee data/sources.csv y devuelve las filas que tienen rango de páginas."""
    with open(SOURCES, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    return [f for f in filas if f["pagina_inicio"] and f["pagina_fin"]]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    PROCESSED.mkdir(parents=True, exist_ok=True)

    for fuente in leer_fuentes():
        inicio, fin = int(fuente["pagina_inicio"]), int(fuente["pagina_fin"])
        texto = extraer_texto(RAW / fuente["archivo"], inicio, fin)
        salida = PROCESSED / f"{fuente['id']}.txt"
        salida.write_text(texto, encoding="utf-8")
        print(f"{fuente['id']:<20} págs. {inicio:>2}-{fin:<2} -> "
              f"{len(texto):6} caracteres, {texto.count(chr(10)):4} líneas -> {salida.name}")


if __name__ == "__main__":
    main()
