"""Paso 2 (continuación): dividir el texto de cada reglamento en artículos.

Lee data/processed/<id>.txt (generado por src/ingest.py) de los documentos de
tipo "reglamento" en data/sources.csv y lo divide en unidades:
- artículos ("Artículo 1.º. Objeto...", "Art. 4.º El tutor académico.-", ...);
- disposiciones ("Disposición final. Entrada en vigor.-", "DISPOSICIÓN ADICIONAL.").

Cada unidad guarda su número, título, la sección a la que pertenece (bloque de la
ESI, o TÍTULO > CAPÍTULO del reglamento de prácticas) y su texto, con las líneas de
cada párrafo unidas. El resultado se guarda en data/processed/articulos/<id>.json.

Método (opción A del diario): se recorre el texto línea a línea y se reconocen los
encabezados con expresiones regulares. Para no confundir un título con una mención
a otro artículo dentro del texto ("...lo dispuesto en el\\nartículo 12.2 del Real
Decreto..."), un título de artículo tiene que:
- empezar por "Artículo" o "Art." con mayúscula;
- tener detrás del número un título que empiece por mayúscula ("12.2 del" no vale);
- llevar el número que toca: el siguiente al último artículo encontrado.

Al terminar comprueba que no se ha perdido ni duplicado ninguna palabra.

Uso (desde la raíz del proyecto, con el entorno activado, después de ingest.py):
    python src/articulos.py
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SOURCES = RAIZ / "data" / "sources.csv"
PROCESSED = RAIZ / "data" / "processed"
SALIDA = PROCESSED / "articulos"

MAYUSCULA = "A-ZÁÉÍÓÚÜÑ"

# "Artículo 1.º. Objeto.-", "Art. 4.º El tutor", "Art. 10. Desarrollo", "Artículo 4.  TFG/M"
TITULO_ARTICULO = re.compile(
    r"^(?:Artículo|Art\.)\s*(?P<numero>\d+)"   # "Artículo 12" o "Art. 12"
    r"\s*(?:\.\s*º|º)?"                         # ".º" o "º" (opcional)
    r"\s*\.?(?!\d)"                             # "." opcional, sin un dígito detrás ("12.2" no)
    r"\s*-?\s*"                                 # "-" opcional
    rf"(?P<titulo>[{MAYUSCULA}].*)$"            # el título empieza por mayúscula
)
# "Disposición final. Entrada en vigor.-", "DISPOSICIÓN ADICIONAL PRIMERA.-", "DISPOSICIONES TRANSITORIAS."
# Tiene que decir de qué tipo es: así "DISPOSICIONES GENERALES" (nombre del Título
# Primero del reglamento de prácticas) no cuenta como disposición.
TITULO_DISPOSICION = re.compile(
    r"^(?:Disposici[oó]n|DISPOSICI[OÓ]N)(?:es|ES)?\s+"
    r"(?i:adicional|transitoria|derogatoria|final)"
)
# Marca de apartado al principio de línea: "1. ", "a)", "iii. ", "3.b)", "•"
INICIO_APARTADO = re.compile(r"^(?:\d+\.(?:\s|$)|\d+\.[a-z]\)|[a-zñ]\)|[ivx]+\.(?:\s|$)|•)")
# Número romano solo ("II.") que podría parecer un encabezado en mayúsculas.
ROMANO_SOLO = re.compile(r"^[IVXL]+\.?$")
# "TÍTULO II.", "CAPÍTULO PRIMERO.": siempre son encabezado de sección, vayan donde vayan.
TITULO_O_CAPITULO = re.compile(
    r"^(?P<nivel>T[ÍI]TULO|CAP[ÍI]TULO)\s+"
    r"(?:[IVXL]+|PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|ÚNICO)\b"
)


def es_titulo_completo(texto: str) -> bool:
    """Un título termina en ".", ".-" o ":". Si no, sigue en la línea siguiente."""
    return bool(re.search(r"[.:]-?\s*$", texto))


def limpiar_titulo(texto: str) -> str:
    """Quita el ".-" o "." final: "Objeto y ámbito de aplicación.-" -> "Objeto y ámbito de aplicación"."""
    return re.sub(r"[\s.:-]+$", "", texto)


def es_encabezado_seccion(linea: str) -> bool:
    """Línea en mayúsculas que puede ser un encabezado de sección ("EL EXAMEN DE TFG/M.")."""
    return (
        any(c.isalpha() for c in linea)
        and linea == linea.upper()
        and not ROMANO_SOLO.match(linea)
        and not TITULO_DISPOSICION.match(linea)
    )


def es_marca_sola(linea: str) -> bool:
    """True si la línea es solo una marca de apartado, sin texto: "a)", "3."."""
    marca = INICIO_APARTADO.match(linea)
    return bool(marca) and linea == marca.group().strip()


def unir_parrafos(lineas: list[str]) -> str:
    """Une las líneas de cada párrafo con un espacio.

    En el PDF cada renglón es una línea aunque la frase continúe. Empieza un párrafo
    nuevo después de una línea vacía o cuando la línea empieza por una marca de
    apartado ("a)", "2. "), para que los apartados queden cada uno en su línea.
    Una marca sola en su línea ("a)") se une con el texto que la sigue.
    """
    parrafos: list[str] = []
    actual: list[str] = []
    for linea in lineas:
        if not linea:  # línea vacía: fin de párrafo
            if actual:
                parrafos.append(" ".join(actual))
                actual = []
            continue
        solo_hay_una_marca = len(actual) == 1 and es_marca_sola(actual[0])
        if INICIO_APARTADO.match(linea) and actual and not solo_hay_una_marca:
            parrafos.append(" ".join(actual))
            actual = []
        actual.append(linea)
    if actual:
        parrafos.append(" ".join(actual))
    return "\n".join(parrafos)


def dividir(documento: str, texto: str) -> tuple[list[dict], list[str], list[str], list[str]]:
    """Divide el texto de un reglamento en artículos y disposiciones.

    Devuelve (unidades, lineas_descartadas, avisos, lineas_seccion):
    - unidades: lista de diccionarios, uno por artículo o disposición, en orden.
    - lineas_descartadas: el texto anterior a la primera unidad (restos del preámbulo).
    - avisos: líneas que parecían un título de artículo pero no llevaban el número
      que tocaba, y que por eso se han tratado como texto normal.
    - lineas_seccion: las líneas de encabezado de sección ("EL EXAMEN DE TFG/M.").
    """
    lineas = texto.splitlines()
    unidades: list[dict] = []
    descartadas: list[str] = []
    avisos: list[str] = []
    secciones: list[str] = []      # ruta actual, p. ej. ["TÍTULO II. ...", "CAPÍTULO I. ..."]
    lineas_seccion: list[str] = [] # líneas de encabezado de sección (para la comprobación)
    actual: dict | None = None     # unidad que se está rellenando
    siguiente = 1                  # número del próximo artículo esperado
    n_disposiciones = 0
    anterior_fue_seccion = False   # la línea anterior era un encabezado de sección

    def cerrar_actual() -> None:
        if actual is not None:
            actual["texto"] = unir_parrafos(actual.pop("_lineas"))
            unidades.append(actual)

    i = 0
    while i < len(lineas):
        linea = lineas[i]
        anterior = lineas[i - 1] if i > 0 else ""
        posterior = lineas[i + 1] if i + 1 < len(lineas) else ""
        m_art = TITULO_ARTICULO.match(linea)
        m_nivel = TITULO_O_CAPITULO.match(linea)
        # Un encabezado de sección está en mayúsculas y además es "TÍTULO .../CAPÍTULO ...",
        # o sigue a otro encabezado, o tiene al menos dos palabras y está pegado a una
        # línea vacía. Así "TFG/M." (final de un párrafo partido) no cuenta como sección.
        es_seccion = es_encabezado_seccion(linea) and bool(
            m_nivel
            or anterior_fue_seccion
            or (len(linea.split()) >= 2 and (not anterior or not posterior))
        )

        # 1. ¿Título de artículo?
        if m_art and int(m_art["numero"]) != siguiente:
            avisos.append(f"línea {i + 1}: {linea!r} (se esperaba el artículo {siguiente})")
            m_art = None
        if m_art or TITULO_DISPOSICION.match(linea):
            cabecera = [linea]
            titulo = m_art["titulo"] if m_art else linea
            # El título puede seguir en la línea siguiente (Art. 9.º del reglamento marco).
            while not es_titulo_completo(titulo) and i + 1 < len(lineas) and lineas[i + 1]:
                i += 1
                cabecera.append(lineas[i])
                titulo += " " + lineas[i]
            cerrar_actual()
            if m_art:
                numero = int(m_art["numero"])
                id_unidad, tipo = f"{documento}_art_{numero}", "articulo"
                siguiente += 1
            else:
                numero = None
                n_disposiciones += 1
                id_unidad, tipo = f"{documento}_disp_{n_disposiciones}", "disposicion"
                secciones = []  # las disposiciones van fuera de los títulos y capítulos
            actual = {
                "id": id_unidad,
                "documento": documento,
                "tipo": tipo,
                "numero": numero,
                "titulo": limpiar_titulo(titulo),
                "seccion": " > ".join(secciones),
                "encabezado": " ".join(cabecera),
                "_lineas": [],
            }

        # 2. ¿Encabezado de sección?
        elif es_seccion:
            lineas_seccion.append(linea)
            if m_nivel and m_nivel["nivel"].startswith("T"):  # TÍTULO: empieza una ruta nueva
                secciones = [linea]
            elif m_nivel:  # CAPÍTULO: va dentro del TÍTULO actual, si lo hay
                secciones = [s for s in secciones[:1] if TITULO_O_CAPITULO.match(s)
                             and s.startswith("T")] + [linea]
            elif anterior_fue_seccion and secciones:
                # "CAPÍTULO II." + "MODALIDADES. RÉGIMEN JURÍDICO" -> "CAPÍTULO II. MODALIDADES..."
                secciones[-1] = limpiar_titulo(secciones[-1]) + ". " + linea
            else:  # sección sin TÍTULO/CAPÍTULO, como los bloques de la ESI
                secciones = [linea]
            secciones = [limpiar_titulo(s) for s in secciones]

        # 3. Texto normal: va al artículo actual, o se descarta si aún no ha empezado ninguno.
        elif actual is not None:
            actual["_lineas"].append(linea)
        else:
            descartadas.append(linea)

        anterior_fue_seccion = es_seccion and not (m_art or TITULO_DISPOSICION.match(linea))
        i += 1

    cerrar_actual()
    return unidades, descartadas, avisos, lineas_seccion


def palabras(texto: str) -> list[str]:
    return texto.split()


def comprobar(texto: str, unidades, descartadas, lineas_seccion) -> list[str]:
    """Comprueba que cada palabra del texto acaba en un único sitio. Devuelve los errores."""
    errores = []
    # Palabras del original frente a palabras repartidas entre encabezados, textos,
    # secciones y lo descartado. Deben ser exactamente las mismas (como multiconjunto).
    repartido = collections.Counter()
    for u in unidades:
        repartido.update(palabras(u["encabezado"]))
        repartido.update(palabras(u["texto"]))
    for linea in lineas_seccion + descartadas:
        repartido.update(palabras(linea))
    original = collections.Counter(palabras(texto))
    if repartido != original:
        faltan = original - repartido
        sobran = repartido - original
        errores.append(f"palabras perdidas: {dict(faltan)} / duplicadas: {dict(sobran)}")

    numeros = [u["numero"] for u in unidades if u["tipo"] == "articulo"]
    if numeros != list(range(1, len(numeros) + 1)):
        errores.append(f"artículos no consecutivos desde 1: {numeros}")
    vacias = [u["id"] for u in unidades if not u["texto"]]
    if vacias:
        errores.append(f"unidades sin texto: {vacias}")
    return errores


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    SALIDA.mkdir(parents=True, exist_ok=True)
    with open(SOURCES, encoding="utf-8", newline="") as f:
        reglamentos = [r for r in csv.DictReader(f) if r["tipo"] == "reglamento"]

    hay_errores = False
    for fuente in reglamentos:
        texto = (PROCESSED / f"{fuente['id']}.txt").read_text(encoding="utf-8")
        unidades, descartadas, avisos, lineas_seccion = dividir(fuente["id"], texto)

        ruta = SALIDA / f"{fuente['id']}.json"
        ruta.write_text(json.dumps(unidades, ensure_ascii=False, indent=2), encoding="utf-8")

        errores = comprobar(texto, unidades, descartadas, lineas_seccion)
        hay_errores |= bool(errores)
        n_art = sum(u["tipo"] == "articulo" for u in unidades)
        print(f"\n{'✓' if not errores else '✗'} {fuente['id']}: {n_art} artículos, "
              f"{len(unidades) - n_art} disposiciones -> {ruta.relative_to(RAIZ)}")
        print(f"  descartado antes del primer artículo: {len(palabras(' '.join(descartadas)))} palabras")
        secciones = list(dict.fromkeys(u["seccion"] for u in unidades if u["seccion"]))
        print(f"  secciones: {len(secciones)}")
        for aviso in avisos:
            print(f"  aviso: posible título ignorado en {aviso}")
        for error in errores:
            print(f"  ✗ {error}")

    sys.exit(1 if hay_errores else 0)


if __name__ == "__main__":
    main()
