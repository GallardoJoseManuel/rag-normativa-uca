"""Valida que data/processed/ conserva todo el contenido de los PDFs.

Para cada documento de data/sources.csv con rango de páginas, compara palabra por
palabra el texto original del PDF (mismo rango, con get_text() sin limpiar) con
data/processed/<id>.txt, generado por src/ingest.py, y comprueba:

1. Que no se ha AÑADIDO texto. ingest.py solo debe quitar, nunca inventar.
   La única excepción admitida es una palabra a la que se le ha quitado una
   llamada de nota pegada ("momento.2" -> "momento.").
2. Qué se ha QUITADO. No se puede decidir automáticamente si es ruido o contenido
   útil, así que se muestra para revisarlo a mano: deberían ser solo membretes,
   números de página, notas al pie y sus llamadas.
3. Que no quedan caracteres de control ni espacios no separables (\\xa0).
4. Que los artículos detectados son consecutivos y no se repiten.

Uso (desde la raíz del proyecto, con el entorno activado, después de ingest.py):
    python scripts/validar_extraccion.py

Termina con código de salida 1 si alguna comprobación automática (1, 3 o 4) falla.
"""
import collections
import csv
import difflib
import re
import sys
from pathlib import Path

import pymupdf

RAIZ = Path(__file__).resolve().parent.parent
SOURCES = RAIZ / "data" / "sources.csv"
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"

CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
ARTICULO = re.compile(r"^(?:Art[ií]culo|Art\.)\s*(\d+)", re.MULTILINE)


def palabras(texto: str) -> list[str]:
    """Divide en palabras, ignorando caracteres de control y espacios no separables."""
    return CONTROL.sub("", texto).replace("\xa0", " ").split()


def es_llamada_quitada(original: list[str], nuevo: list[str]) -> bool:
    """True si el cambio es solo quitar un número pegado al final: "momento.2" -> "momento."."""
    return (
        len(original) == len(nuevo) == 1
        and original[0].startswith(nuevo[0])
        and original[0][len(nuevo[0]):].isdigit()
    )


def validar(fuente: dict) -> bool:
    """Valida un documento, imprime el informe y devuelve True si todo es correcto."""
    inicio, fin = int(fuente["pagina_inicio"]), int(fuente["pagina_fin"])
    doc = pymupdf.open(RAW / fuente["archivo"])
    original = palabras("\n".join(doc[i].get_text() for i in range(inicio - 1, fin)))

    ruta = PROCESSED / f"{fuente['id']}.txt"
    if not ruta.exists():
        print(f"\n✗ {fuente['id']}: no existe {ruta.name}. Ejecuta antes src/ingest.py")
        return False
    texto = ruta.read_text(encoding="utf-8")
    procesado = palabras(texto)

    # SequenceMatcher encuentra los tramos comunes y describe el resto como
    # operaciones: "delete" (quitado), "insert" (añadido) o "replace" (cambiado).
    comparacion = difflib.SequenceMatcher(None, original, procesado, autojunk=False)
    # Lo quitado se agrupa ignorando los números, para que el membrete de cada
    # página ("... pág. 4", "... pág. 5") cuente como un solo fragmento repetido.
    quitado = collections.Counter()
    ejemplo = {}
    anadido = []

    def registrar_quitado(fragmento: str) -> None:
        clave = re.sub(r"\d+", "#", fragmento)
        quitado[clave] += 1
        ejemplo.setdefault(clave, fragmento)

    for operacion, a1, a2, b1, b2 in comparacion.get_opcodes():
        if operacion == "equal":
            continue
        if operacion == "replace" and es_llamada_quitada(original[a1:a2], procesado[b1:b2]):
            registrar_quitado(original[a1])
            continue
        if a2 > a1:
            registrar_quitado(" ".join(original[a1:a2]))
        if b2 > b1:
            anadido.append(" ".join(procesado[b1:b2]))

    caracteres_raros = len(CONTROL.findall(texto)) + texto.count("\xa0")
    articulos = [int(n) for n in ARTICULO.findall(texto)]
    consecutivos = all(b == a + 1 for a, b in zip(articulos, articulos[1:]))

    correcto = not anadido and caracteres_raros == 0 and consecutivos
    print(f"\n{'✓' if correcto else '✗'} {fuente['id']} (págs. {inicio}-{fin}): "
          f"{len(original)} palabras en el PDF -> {len(procesado)} procesadas "
          f"({len(original) - len(procesado)} quitadas)")

    if anadido:
        print("  ✗ TEXTO AÑADIDO (no debería haber nada):")
        for fragmento in anadido:
            print(f"      {fragmento[:100]!r}")
    if caracteres_raros:
        print(f"  ✗ Quedan {caracteres_raros} caracteres de control o \\xa0")
    if articulos:
        estado = "✓" if consecutivos else "✗ NO consecutivos o repetidos:"
        print(f"  {estado} {len(articulos)} artículos, del {articulos[0]} al {articulos[-1]}"
              + ("" if consecutivos else f" {articulos}"))
    if quitado:
        print("  Quitado (revisar que sea solo ruido):")
        for clave, veces in quitado.most_common():
            print(f"    {veces:>3}x  {ejemplo[clave][:100]}")
    return correcto


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    with open(SOURCES, encoding="utf-8", newline="") as f:
        fuentes = [r for r in csv.DictReader(f) if r["pagina_inicio"] and r["pagina_fin"]]

    resultados = [validar(fuente) for fuente in fuentes]
    fallos = resultados.count(False)
    print(f"\n{len(resultados) - fallos}/{len(resultados)} documentos superan las "
          f"comprobaciones automáticas. Revisa a mano la sección 'Quitado' de cada uno.")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
