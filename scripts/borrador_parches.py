"""Genera un BORRADOR de data/parches.json a partir de las dos modificaciones.

No escribe el archivo definitivo: deja el borrador en
data/processed/parches_borrador.json para revisarlo a mano. Cada parche lleva:
- "revisado": false  -> hay que revisarlo y cambiarlo a true;
- "revisar": [...]    -> avisos sobre lo que el script no ha podido decidir solo.
Después de revisar, se guarda como data/parches.json (ese sí va al repositorio).

Cómo se construye:
- Modificación de 2015 (prácticas): automático. Todos sus cambios siguen el esquema
  "el apartado X del artículo N queda redactado como sigue: <<texto nuevo>>". Se
  extrae el artículo y cada bloque <<...>>, y se busca en el artículo original el
  apartado con la misma marca ("2.", "b)", "iii.") para proponer el texto antiguo.
- Modificación de 2014 (TFG): sus cambios son de tipos distintos (añadir un capítulo,
  renumerar, añadir frases), así que se escriben a mano en borrador_2014(). Los
  textos largos (los artículos 9-13 nuevos) sí se extraen del documento.

Operaciones (se aplican en el orden de la lista):
- reemplazar_texto:    cambia `texto_antiguo` por `texto_nuevo` dentro del artículo.
- reemplazar_articulo: sustituye título y texto de un artículo entero.
- renumerar:           cambia el número de un artículo.
- añadir_articulo:     inserta un artículo nuevo.
- asignar_seccion:     pone la sección (capítulo) de una lista de artículos.

Uso (desde la raíz del proyecto, después de ingest.py y articulos.py):
    python scripts/borrador_parches.py
"""
import difflib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from articulos import INICIO_APARTADO, unir_parrafos  # noqa: E402

PROCESSED = RAIZ / "data" / "processed"
SALIDA = PROCESSED / "parches_borrador.json"

NUMERALES = ["Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete", "Ocho", "Nueve",
             "Diez", "Once", "Doce", "Trece", "Catorce", "Quince", "Dieciséis",
             "Diecisiete", "Dieciocho", "Diecinueve", "Veinte"]
INICIO_CAMBIO = re.compile(rf"^(?P<cambio>{'|'.join(NUMERALES)})\.-")
ARTICULO_COMPLETO = re.compile(r"^Art[íi]culo (?P<numero>\d+)\.\s*(?P<titulo>.+?)\.-\s*(?P<texto>.*)$", re.S)

# Marcas al principio de un bloque <<...>>, de la más específica a la más general.
MARCAS = [
    ("num_letra", re.compile(r"^(?P<num>\d+)\.(?P<letra>[a-z])\)\s*(?P<resto>.*)$", re.S)),          # "3.b) el horario"
    ("letra_romano", re.compile(r"^(?P<letra>[a-z])\)\.?\s*(?P<romano>[ivx]+)\.?\s+(?P<resto>.*)$", re.S)),  # "d). iii perdida"
    ("num", re.compile(r"^(?P<num>\d+)\.\s+(?P<resto>.*)$", re.S)),                                 # "2. Las prácticas"
    ("letra", re.compile(r"^(?P<letra>[a-zñ])\)\s*(?P<resto>.*)$", re.S)),                          # "i) Realizar"
]


def cargar_articulos(documento: str) -> dict[int, dict]:
    unidades = json.loads((PROCESSED / "articulos" / f"{documento}.json").read_text(encoding="utf-8"))
    return {u["numero"]: u for u in unidades if u["tipo"] == "articulo"}


def normalizar(bloque: str) -> str:
    """Une las líneas del bloque en párrafos, igual que articulos.py con los artículos."""
    return unir_parrafos([linea.strip() for linea in bloque.strip().splitlines()])


def rango_apartado(parrafos: list[str], numero: int) -> tuple[int, int] | None:
    """Índices [inicio, fin) de los párrafos del apartado `numero` ("2. ..." hasta "3. ...")."""
    inicio = next((i for i, p in enumerate(parrafos) if p.startswith(f"{numero}. ")), None)
    if inicio is None:
        return None
    fin = next((i for i in range(inicio + 1, len(parrafos)) if re.match(r"^\d+\. ", parrafos[i])),
               len(parrafos))
    return inicio, fin


def buscar(parrafos: list[str], tipo: str, m: re.Match) -> tuple[int, int] | None:
    """Localiza en el artículo original los párrafos que corresponden a la marca del bloque."""
    if tipo == "num":
        return rango_apartado(parrafos, int(m["num"]))
    if tipo == "num_letra":
        apartado = rango_apartado(parrafos, int(m["num"]))
        if apartado is None:
            return None
        i = next((i for i in range(*apartado) if parrafos[i].startswith(f"{m['letra']}) ")), None)
        return (i, i + 1) if i is not None else None
    if tipo == "letra":
        i = next((i for i, p in enumerate(parrafos) if p.startswith(f"{m['letra']}) ")), None)
        return (i, i + 1) if i is not None else None
    if tipo == "letra_romano":
        letra = next((i for i, p in enumerate(parrafos) if p.startswith(f"{m['letra']}) ")), None)
        if letra is None:
            return None
        i = next((i for i in range(letra + 1, len(parrafos))
                  if parrafos[i].startswith(f"{m['romano']}. ")), None)
        return (i, i + 1) if i is not None else None
    return None


def palabras_distintas(antiguo: str, nuevo: str) -> int:
    """Cuántas palabras cambian entre los dos textos (para orientar la revisión)."""
    a, b = antiguo.split(), nuevo.split()
    iguales = sum(bloque.size for bloque in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return max(len(a), len(b)) - iguales


def borrador_2015() -> list[dict]:
    documento, reglamento = "practicas_uca_2015", "practicas_uca_2012"
    articulos = cargar_articulos(reglamento)
    lineas = (PROCESSED / f"{documento}.txt").read_text(encoding="utf-8").splitlines()

    # Agrupar las líneas de cada cambio ("Uno.-" ... hasta el siguiente o la disposición final).
    cambios: list[tuple[str, list[str]]] = []
    for linea in lineas:
        if m := INICIO_CAMBIO.match(linea):
            cambios.append((m["cambio"], [linea]))
        elif linea.startswith("Disposición final"):
            break
        elif cambios:
            cambios[-1][1].append(linea)

    parches = []
    for cambio, lineas_cambio in cambios:
        texto = "\n".join(lineas_cambio)
        enunciado = " ".join(texto.split("<<")[0].split())
        bloques = [normalizar(b) for b in re.findall(r"<<(.*?)>>", texto, re.S)]
        numeros = set(re.findall(r"art[íi]culo (\d+)", enunciado))
        base = {"fuente": documento, "cambio": cambio, "enunciado": enunciado, "reglamento": reglamento}

        if len(numeros) != 1:
            parches.append({**base, "operacion": "?", "revisado": False,
                            "revisar": [f"no sé a qué artículo afecta: {sorted(numeros)}"]})
            continue
        numero = int(numeros.pop())
        parrafos = articulos[numero]["texto"].split("\n")

        # Apartados que nombra el enunciado ("Los apartados 1, 6 y 12 del artículo 22").
        nombrados = re.search(r"apartados? ([\d, y]+?) del", enunciado)
        nombrados = set(re.findall(r"\d+", nombrados.group(1))) if nombrados else set()
        en_bloques = {m.group(1) for b in bloques if (m := re.match(r"^(\d+)\. ", b))}
        aviso_enunciado = (
            [f"el enunciado nombra los apartados {sorted(nombrados)} pero los bloques traen "
             f"{sorted(en_bloques)}: comprobar cuál es la intención"]
            if nombrados and en_bloques and nombrados != en_bloques else []
        )

        for bloque in bloques:
            if m := ARTICULO_COMPLETO.match(bloque):
                parches.append({**base, "operacion": "reemplazar_articulo", "articulo": numero,
                                "titulo": m["titulo"].strip(), "texto_nuevo": m["texto"].strip(),
                                "revisado": False, "revisar": []})
                continue

            revisar = list(aviso_enunciado)
            tipo, marca = next(((t, r.match(bloque)) for t, r in MARCAS if r.match(bloque)), (None, None))
            if tipo:
                rango = buscar(parrafos, tipo, marca)
            elif "último párrafo" in enunciado:
                rango = (len(parrafos) - 1, len(parrafos))
                revisar.append("bloque sin marca: se ha supuesto que es el último párrafo del artículo")
            else:
                rango = None

            if rango is None:
                parches.append({**base, "operacion": "reemplazar_texto", "articulo": numero,
                                "texto_antiguo": "", "texto_nuevo": bloque, "revisado": False,
                                "revisar": revisar + ["no encuentro el texto antiguo: rellenarlo a mano"]})
                continue

            antiguo = "\n".join(parrafos[rango[0]:rango[1]])
            if tipo:
                # Mantener el formato de marca del original: "3.b) el" -> "b) el", "d). iii x" -> "iii. x"
                marca_original = INICIO_APARTADO.match(parrafos[rango[0]]).group().strip()
                nuevo = f"{marca_original} {marca['resto'].strip()}"
                if tipo in ("num_letra", "letra_romano"):
                    revisar.append(f"marca compuesta en el original ('{bloque.split()[0]}'): "
                                   f"se ha escrito como '{marca_original}'")
            else:
                nuevo = bloque
            if rango[1] - rango[0] > 1:
                revisar.append(f"el texto antiguo ocupa {rango[1] - rango[0]} párrafos: comprobar que "
                               f"el nuevo los sustituye todos")
            cambiadas = palabras_distintas(antiguo, nuevo)
            if cambiadas == 0:
                revisar.append("el texto nuevo es IGUAL al antiguo: ¿hace falta este parche?")
            parches.append({**base, "operacion": "reemplazar_texto", "articulo": numero,
                            "texto_antiguo": antiguo, "texto_nuevo": nuevo,
                            "palabras_que_cambian": cambiadas, "revisado": False, "revisar": revisar})
    return parches


def borrador_2014() -> list[dict]:
    """Cambios de 2014, escritos a mano: cada uno es de un tipo distinto."""
    documento, reglamento = "tfg_uca_2014", "tfg_uca_2012"
    articulos = cargar_articulos(reglamento)
    texto = (PROCESSED / f"{documento}.txt").read_text(encoding="utf-8")
    base = {"fuente": documento, "reglamento": reglamento}

    def seccion(nombre: str) -> str:
        """'Capítulo II.' + las líneas siguientes hasta una línea vacía -> nombre de la sección."""
        m = re.search(rf"^Capítulo {nombre}\.\n((?:.+\n)+?)(?:\n|-\n)", texto, re.M)
        return f"Capítulo {nombre}. " + " ".join(m.group(1).split())

    # PRIMERO: los artículos 9-13 nuevos, entre "Capítulo II." y "SEGUNDO."
    bloque = texto[texto.index("Capítulo II."):texto.index("SEGUNDO.")]
    trozos = re.split(r"^Art\. (\d+)\.?º?\.?-?\s*", bloque, flags=re.M)[1:]
    nuevos = []
    for numero, contenido in zip(trozos[0::2], trozos[1::2]):
        primera, _, resto = contenido.partition("\n")
        # Si la primera línea es corta y acaba en punto es el título; si no, ya es texto (Art. 13).
        if primera.strip().endswith(".") and len(primera) < 100:
            titulo, cuerpo, revisar = primera.strip().rstrip("."), resto, []
        else:
            titulo, cuerpo = "", contenido
            revisar = ["este artículo no tiene título en la modificación: ¿dejarlo vacío o ponerle uno?"]
        nuevos.append({**base, "cambio": "PRIMERO", "operacion": "añadir_articulo",
                       "articulo": int(numero), "titulo": titulo,
                       "texto_nuevo": normalizar(cuerpo), "revisado": False, "revisar": revisar})

    frase_tercero = ", en los términos en que lo apruebe las comisión competente"
    frase_cuarto = ", sin perjuicio de aquellos requisitos adicionales establecidos en las memorias de los títulos"
    antiguo_6 = "que ejercerá como tutor del trabajo."
    antiguo_2 = next(p for p in articulos[2]["texto"].split("\n") if p.startswith("5. "))

    return [
        # SEGUNDO va primero: hay que renumerar 9 y 10 antes de añadir los nuevos 9-13.
        {**base, "cambio": "SEGUNDO", "operacion": "renumerar", "articulo": 9, "nuevo_numero": 14,
         "revisado": False, "revisar": []},
        {**base, "cambio": "SEGUNDO", "operacion": "renumerar", "articulo": 10, "nuevo_numero": 15,
         "revisado": False, "revisar": []},
        *nuevos,
        {**base, "cambio": "SEGUNDO", "operacion": "asignar_seccion", "articulos": list(range(1, 9)),
         "seccion": seccion("primero"), "revisado": False, "revisar": []},
        {**base, "cambio": "PRIMERO", "operacion": "asignar_seccion", "articulos": list(range(9, 14)),
         "seccion": seccion("II"), "revisado": False, "revisar": []},
        {**base, "cambio": "SEGUNDO", "operacion": "asignar_seccion", "articulos": [14, 15],
         "seccion": seccion("III"), "revisado": False, "revisar": []},
        {**base, "cambio": "TERCERO", "operacion": "reemplazar_texto", "articulo": 6,
         "texto_antiguo": antiguo_6, "texto_nuevo": antiguo_6[:-1] + frase_tercero + ".",
         "revisado": False, "revisar": [
             "'párrafo cuarto del artículo 6.º': en el PDF el 4.º párrafo es 'Además, los alumnos "
             "podrán proponer...', que termina en 'tutor del trabajo'. En nuestro texto aparece unido "
             "al 3.º porque estaba al principio de una página nueva. Comprobarlo en el PDF (p. 7)",
             "'las comisión' es una errata del original: ¿se copia tal cual o se corrige?"]},
        {**base, "cambio": "CUARTO", "operacion": "reemplazar_texto", "articulo": 2,
         "texto_antiguo": antiguo_2, "texto_nuevo": antiguo_2[:-1] + frase_cuarto + ".",
         "revisado": False, "revisar": [
             "el enunciado dice 'se añadirá la frase' sin decir dónde: se ha puesto antes del punto "
             "final, como en el cambio TERCERO"]},
    ]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    parches = borrador_2014() + borrador_2015()
    SALIDA.write_text(json.dumps(parches, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Borrador con {len(parches)} parches -> {SALIDA.relative_to(RAIZ)}\n")
    for p in parches:
        destino = p.get("articulo", p.get("articulos"))
        print(f"  {p['fuente'][-4:]} {p['cambio']:<10} {p['operacion']:<20} art. {destino}")
        for aviso in p["revisar"]:
            print(f"      ⚠ {aviso}")
    print(f"\n{sum(bool(p['revisar']) for p in parches)} parches tienen avisos. Revisa TODOS, "
          "pon \"revisado\": true y guarda el resultado como data/parches.json")


if __name__ == "__main__":
    main()
