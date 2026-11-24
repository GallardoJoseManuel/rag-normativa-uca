"""Paso 2 del pipeline: extracción y limpieza del texto de los PDFs del corpus.

Para cada documento de data/sources.csv que tenga rango de páginas útil
(pagina_inicio, pagina_fin), extrae el texto de esas páginas, lo limpia y lo
guarda en data/processed/<id>.txt para poder revisarlo.

Limpieza aplicada (conclusiones del análisis exploratorio, docs/diario.md):
- Quita las notas al pie (letra más pequeña que el cuerpo y situadas debajo de
  él), sus llamadas ("vigente 1" -> "vigente") y los membretes en letra pequeña.
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
# Los tamaños de letra se comparan con el del cuerpo de cada documento (10, 11 o
# 12 pt según el PDF), así que las reglas funcionan aunque cada uno use otro tamaño.
# - Texto más de MARGEN_TAMANO puntos menor que el cuerpo: se quita esté donde esté
#   (llamadas de nota, membretes y notas al pie en letra muy pequeña).
MARGEN_TAMANO = 2.0
# - Texto algo menor que el cuerpo (más de TOLERANCIA_TAMANO puntos): se quita solo si
#   está debajo del cuerpo de la página, que es donde van las notas al pie. En otro
#   sitio puede ser contenido real en letra un poco menor, y se conserva.
TOLERANCIA_TAMANO = 0.5


def limpiar_linea(linea: str) -> str:
    """Quita caracteres de control, normaliza espacios y recorta la línea."""
    linea = CONTROL.sub("", linea)           # 1. borra los caracteres de control
    linea = linea.replace("\xa0", " ")       # 2. espacio no separable -> espacio normal
    linea = re.sub(r"[ \t]+", " ", linea)    # 3. varios espacios seguidos -> uno
    return linea.strip()                     # 4. quita espacios al principio y al final


def lineas_pagina(page: pymupdf.Page, cuerpo: float | None = None) -> list[str]:
    """Devuelve las líneas limpias de una página.

    get_text("dict") da el texto por bloques -> líneas -> spans. Un span es un
    trozo de texto con el mismo formato y trae su tamaño de letra ("size") y cada
    línea su posición en la página ("bbox": x0, y0, x1, y1; la y crece hacia abajo).

    Si se indica el tamaño del `cuerpo`, quita el texto pequeño:
    - Spans más de MARGEN_TAMANO puntos menores que el cuerpo, estén donde estén.
      Si la línea pierde algún span se queda el resto ("vigente 1 y" -> "vigente y");
      si los pierde todos, se descarta entera.
    - Líneas enteras algo menores que el cuerpo situadas por debajo de la última
      línea del cuerpo de la página: son notas al pie.
    Las líneas vacías se conservan, porque separan párrafos.
    """
    lineas_pdf = [
        linea
        for bloque in page.get_text("dict")["blocks"]
        for linea in bloque.get("lines", [])  # los bloques de imagen no tienen "lines"
    ]
    if cuerpo is None:  # sin filtro de tamaño
        return [limpiar_linea("".join(s["text"] for s in l["spans"])) for l in lineas_pdf]

    def tiene_texto(span) -> bool:
        return bool(span["text"].strip())

    def es_del_cuerpo(span) -> bool:
        return abs(span["size"] - cuerpo) <= TOLERANCIA_TAMANO

    # Dónde termina el cuerpo en esta página: el borde inferior (y1) de la última
    # línea con texto del tamaño del cuerpo. Las notas al pie quedan por debajo.
    fin_cuerpo = max(
        (l["bbox"][3] for l in lineas_pdf
         if any(es_del_cuerpo(s) and tiene_texto(s) for s in l["spans"])),
        default=None,
    )

    lineas = []
    for linea in lineas_pdf:
        con_texto = [s for s in linea["spans"] if tiene_texto(s)]
        if not con_texto:
            lineas.append("")  # línea vacía: separa párrafos
            continue

        debajo_del_cuerpo = fin_cuerpo is not None and linea["bbox"][1] >= fin_cuerpo
        menor_que_cuerpo = all(s["size"] < cuerpo - TOLERANCIA_TAMANO for s in con_texto)
        if debajo_del_cuerpo and menor_que_cuerpo:
            continue  # nota al pie

        conservados = [s["text"] for s in linea["spans"] if s["size"] >= cuerpo - MARGEN_TAMANO]
        if not any(t.strip() for t in conservados):
            continue  # toda la línea era texto muy pequeño
        lineas.append(limpiar_linea("".join(conservados)))
    return lineas


def tamano_cuerpo(doc: pymupdf.Document, pagina_inicio: int, pagina_fin: int) -> float:
    """Devuelve el tamaño de letra del cuerpo: el que tiene más caracteres en el rango."""
    caracteres_por_tamano = collections.Counter()
    for num in range(pagina_inicio - 1, pagina_fin):
        for bloque in doc[num].get_text("dict")["blocks"]:
            for linea in bloque.get("lines", []):
                for span in linea["spans"]:
                    caracteres_por_tamano[round(span["size"], 1)] += len(span["text"].strip())
    tamano, _ = caracteres_por_tamano.most_common(1)[0]
    return tamano


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
        lineas = set(lineas_pagina(page))  # set: una vez por página
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
    cuerpo = tamano_cuerpo(doc, pagina_inicio, pagina_fin)
    paginas = []
    for num in range(pagina_inicio - 1, pagina_fin):  # de numeración 1.. a 0..
        lineas = []
        for linea in lineas_pagina(doc[num], cuerpo):
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
