"""Exploración automática de los PDFs del corpus con PyMuPDF.

Para cada PDF de data/raw/ muestra, página a página:
- número de caracteres extraídos,
- tablas detectadas por PyMuPDF,
- líneas que parecen títulos de artículo, capítulo o disposición.

Y para el documento completo:
- líneas que se repiten en muchas páginas (posibles encabezados o pies),
- caracteres de control (invisibles en el visor de PDF).

Uso (desde la raíz del proyecto, con el entorno activado):
    python scripts/explorar_pdfs.py
"""
import collections
import re
import sys
from pathlib import Path

import pymupdf

# En la consola de Windows, forzar UTF-8 para que se vean bien las tildes.
sys.stdout.reconfigure(encoding="utf-8")

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

# "Artículo 1.", "Artículo 1.º", "Art. 2.º", "Art. 10." ...
PATRON_ARTICULO = re.compile(r"^\s*(Art[ií]culo|Art\.)\s*\d+", re.IGNORECASE)
PATRON_BLOQUE = re.compile(
    r"^\s*(T[ÍI]TULO|CAP[ÍI]TULO|Disposici[oó]n|DISPOSICI[OÓ]N|ANEXO)", re.IGNORECASE
)


def explorar(pdf_path: Path) -> None:
    doc = pymupdf.open(pdf_path)
    print(f"\n{'=' * 80}\n{pdf_path.name}: {len(doc)} páginas")

    repetidas = collections.Counter()  # en cuántas páginas aparece cada línea
    total_chars = 0

    for num, page in enumerate(doc, start=1):
        texto = page.get_text()
        total_chars += len(texto)
        lineas = [l.strip() for l in texto.splitlines() if l.strip()]
        repetidas.update(set(lineas))  # set: contar cada línea una vez por página
        tablas = page.find_tables().tables

        if not lineas:
            print(f"  p{num:02}: SIN TEXTO (¿PDF escaneado?)")
            continue
        print(f"  p{num:02}: {len(texto):5} chars | tablas: {len(tablas)} | "
              f"empieza: {lineas[0][:60]!r}")
        for l in lineas:
            if PATRON_ARTICULO.match(l) or PATRON_BLOQUE.match(l):
                print(f"         · {l[:90]}")

    print(f"  total caracteres: {total_chars}")

    # Una línea que sale en al menos la mitad de las páginas suele ser un encabezado o pie.
    if len(doc) > 2:
        umbral = max(3, len(doc) // 2)
        candidatas = [l[:50] for l, n in repetidas.items() if n >= umbral]
        print(f"  líneas repetidas en >= {umbral} páginas: {candidatas}")

    completo = "".join(p.get_text() for p in doc)
    controles = collections.Counter(
        c for c in completo if ord(c) < 32 and c not in "\n\t"
    )
    print("  caracteres de control:", {repr(c): n for c, n in controles.items()})


if __name__ == "__main__":
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No hay PDFs en {RAW}. Descárgalos según data/sources.csv.")
    for pdf in pdfs:
        explorar(pdf)
