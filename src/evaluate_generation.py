"""Paso 7: evalúa las respuestas del RAG completo (búsqueda + LLM) con eval/questions.json.

Para cada pregunta genera la respuesta con generate.py y mide:

- Abstención (con código, exacto): en las preguntas "sin_respuesta" el sistema debe decir
  que no lo encuentra (encontrado = false); en las demás, no debe abstenerse.
- Citas (con código, exacto): de los artículos que cita, cuántos están entre las fuentes
  correctas de la pregunta.
- Corrección y fidelidad (con un LLM como juez): el juez recibe la pregunta, la respuesta
  de referencia, la respuesta del sistema y los fragmentos que leyó, y decide si la
  respuesta es correcta / parcial / incorrecta y si todo lo que afirma está en los
  fragmentos. Siempre con una justificación.

El juez también se equivoca: con --calibracion se crea eval/calibracion.csv con una muestra
de respuestas para corregir a mano (sin ver lo que dijo el juez), y con --acuerdo se mide
cuántas veces coincide el juez con la corrección humana.

El progreso se guarda después de cada pregunta: si el nivel gratuito corta a medias, al
volver a ejecutar se continúa donde se quedó (--de-nuevo para empezar de cero).

Uso (desde la raíz del proyecto, después de index.py; necesita GEMINI_API_KEY en .env):
    python src/evaluate_generation.py                # evaluar (unos 10-15 minutos)
    python src/evaluate_generation.py --calibracion  # crear la muestra para corregir a mano
    python src/evaluate_generation.py --acuerdo      # comparar juez y corrección humana
    python src/evaluate_generation.py --rejuzgar     # volver a juzgar tras cambiar la rúbrica
"""
import argparse
import csv
import json
import random
import statistics
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal

from google import genai
from pydantic import BaseModel, Field

from generate import MODELO_LLM, MODELOS_RESERVA, contexto, llamar, responder
from retrieve import Buscador

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = RAIZ / "eval" / "questions.json"
RESULTADOS = RAIZ / "eval" / "resultados"
CALIBRACION = RAIZ / "eval" / "calibracion.csv"

PAUSA = 4          # segundos entre llamadas, para no pasar del límite por minuto gratuito
N_CALIBRACION = 15

INSTRUCCIONES_JUEZ = """Eres un evaluador estricto de un asistente que responde dudas sobre normativa \
universitaria. Recibes una pregunta, una RESPUESTA DE REFERENCIA (correcta, escrita por una persona), \
la RESPUESTA DEL SISTEMA y los FRAGMENTOS de normativa que el sistema leyó.

Evalúa dos cosas por separado:

1. "correccion", comparando la respuesta del sistema con la de referencia:
   - "correcta": contiene los datos esenciales de la referencia y no contradice nada.
   - "parcial": acierta en parte pero le falta algo esencial de la referencia, o añade un \
error menor.
   - "incorrecta": contradice la referencia, da un dato equivocado, no responde a lo que se \
pregunta o dice que no encuentra la información cuando la referencia sí la da.
   Regla obligatoria: si la referencia explica lo que dicen DOS normas o casos (el reglamento \
marco de la UCA y el de la ESI, o las prácticas curriculares y las extracurriculares) y la \
respuesta del sistema solo da uno de ellos, la corrección es "parcial", aunque lo que diga sea \
cierto y esté bien explicado.
   No premies la longitud ni el estilo: solo importa el contenido. Los datos adicionales \
ciertos que no estén en la referencia no restan.

2. "fiel": true si TODO lo que afirma la respuesta del sistema está respaldado por los \
fragmentos; false si afirma algo que no aparece en ellos, aunque sea cierto. Antes de marcar \
false, busca la afirmación en todos los fragmentos: si alguno la dice, aunque sea con otras \
palabras, es fiel.

Justifica cada decisión en una o dos frases."""


class Veredicto(BaseModel):
    """Formato que debe devolver el juez."""
    justificacion: str = Field(description="por qué se decide la corrección y la fidelidad, en 1-2 frases")
    correccion: Literal["correcta", "parcial", "incorrecta"]
    fiel: bool


def juzgar(cliente: genai.Client, modelo: str, q: dict, r: dict) -> tuple[Veredicto, str]:
    prompt = (f"PREGUNTA: {q['pregunta']}\n\n"
              f"RESPUESTA DE REFERENCIA: {q['respuesta']}\n\n"
              f"RESPUESTA DEL SISTEMA: {r['respuesta']}\n\n"
              f"FRAGMENTOS QUE LEYÓ EL SISTEMA:\n\n{r['contexto']}")
    return llamar(cliente, [modelo] + [m for m in MODELOS_RESERVA if m != modelo], prompt,
                  INSTRUCCIONES_JUEZ, Veredicto)


def evaluar_una(q: dict, buscador: Buscador, cliente: genai.Client, modelo: str) -> dict:
    """Genera la respuesta de una pregunta y la puntúa."""
    r = responder(q["pregunta"], buscador, cliente, modelo)
    fila = {"id": q["id"], "tipo": q["tipo"], "pregunta": q["pregunta"], "referencia": q["respuesta"],
            "fuentes": q["fuentes"], "respuesta": r["respuesta"], "encontrado": r["encontrado"],
            "citadas": [f["unidad"] for f in r["fuentes"]], "recuperados": r["recuperados"],
            "modelo": r["modelo"]}

    if not q["fuentes"]:  # sin_respuesta: lo correcto es abstenerse; no hace falta juez
        fila["abstencion_correcta"] = not r["encontrado"]
        return fila

    fila["abstencion_correcta"] = r["encontrado"]  # aquí lo correcto es NO abstenerse
    citadas = set(fila["citadas"])
    fila["citas_correctas"] = len(citadas & set(q["fuentes"]))
    fila["citas_total"] = len(citadas)
    time.sleep(PAUSA)
    veredicto, modelo_juez = juzgar(cliente, modelo, q, r)
    fila.update(veredicto.model_dump())
    fila["modelo_juez"] = modelo_juez
    return fila


def nota(f: dict) -> str:
    """Corrección final de una respuesta con fuentes.

    Si el sistema dijo que no lo encontraba en una pregunta que sí tiene respuesta, es
    "incorrecta" según la rúbrica, y eso se decide con código: en la primera evaluación el
    juez lo marcó como "correcta" en varios casos, confundiendo "fiel a lo que leyó" con
    "correcta".
    """
    return "incorrecta" if not f["encontrado"] else f["correccion"]


def resumen(filas: list[dict]) -> dict:
    """Métricas agregadas, en total y por tipo de pregunta."""
    con = [f for f in filas if f["fuentes"]]
    sin = [f for f in filas if not f["fuentes"]]
    citan = [f for f in con if f["citas_total"]]

    def corr(grupo):
        c = Counter(nota(f) for f in grupo)
        return {k: c[k] / len(grupo) for k in ("correcta", "parcial", "incorrecta")}

    return {
        "n_con_respuesta": len(con), "n_sin_respuesta": len(sin),
        "abstencion_bien_sin_respuesta": statistics.mean(f["abstencion_correcta"] for f in sin) if sin else None,
        "falsas_abstenciones": sum(not f["abstencion_correcta"] for f in con) / len(con),
        "precision_citas": sum(f["citas_correctas"] for f in citan) / sum(f["citas_total"] for f in citan),
        "cita_alguna_correcta": statistics.mean(f["citas_correctas"] > 0 for f in con),
        "correccion": corr(con),
        "fidelidad": statistics.mean(f["fiel"] for f in con),
        "por_tipo": {t: {"n": len(g), **corr(g), "fidelidad": statistics.mean(f["fiel"] for f in g)}
                     for t in sorted({f["tipo"] for f in con})
                     for g in [[f for f in con if f["tipo"] == t]]},
    }


def imprimir(m: dict, modelo: str) -> None:
    print(f"\nModelo {modelo} · {m['n_con_respuesta']} preguntas con respuesta, "
          f"{m['n_sin_respuesta']} sin respuesta\n")
    print(f"Abstención correcta en preguntas sin respuesta: {m['abstencion_bien_sin_respuesta']:.0%}")
    print(f"Falsas abstenciones (dice que no está, pero sí está): {m['falsas_abstenciones']:.0%}")
    print(f"Precisión de las citas (citadas que son correctas): {m['precision_citas']:.0%}")
    print(f"Cita al menos un artículo correcto: {m['cita_alguna_correcta']:.0%}")
    c = m["correccion"]
    print(f"Corrección (juez): correcta {c['correcta']:.0%} · parcial {c['parcial']:.0%} · "
          f"incorrecta {c['incorrecta']:.0%}")
    print(f"Fidelidad (juez): {m['fidelidad']:.0%}\n")
    print(f"{'':<12}{'n':>3}{'correcta':>10}{'parcial':>9}{'incorr.':>9}{'fiel':>7}")
    for t, v in m["por_tipo"].items():
        print(f"{t:<12}{v['n']:>3}{v['correcta']:>10.0%}{v['parcial']:>9.0%}"
              f"{v['incorrecta']:>9.0%}{v['fidelidad']:>7.0%}")


def crear_calibracion(filas: list[dict]) -> None:
    """Muestra estratificada por tipo para corregir a mano, SIN el veredicto del juez."""
    con = [f for f in filas if f["fuentes"]]
    azar = random.Random(42)  # semilla fija: la muestra es siempre la misma
    por_tipo = {t: [f for f in con if f["tipo"] == t] for t in sorted({f["tipo"] for f in con})}
    muestra = []
    while len(muestra) < N_CALIBRACION:  # una de cada tipo por turno, hasta llegar a 15
        for grupo in por_tipo.values():
            restantes = [f for f in grupo if f not in muestra]
            if restantes and len(muestra) < N_CALIBRACION:
                muestra.append(azar.choice(restantes))
    # utf-8-sig y ";" para que Excel en español lo abra bien
    with open(CALIBRACION, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "pregunta", "respuesta_referencia", "respuesta_sistema", "humano"])
        for x in sorted(muestra, key=lambda x: x["id"]):
            w.writerow([x["id"], x["pregunta"], x["referencia"], x["respuesta"], ""])
    print(f"✓ {len(muestra)} respuestas -> {CALIBRACION.relative_to(RAIZ)}")
    print("  Rellena la columna 'humano' con: correcta, parcial o incorrecta.")


def acuerdo(filas: list[dict]) -> None:
    """Compara la corrección humana del CSV con la del juez."""
    juez = {f["id"]: f for f in filas if f["fuentes"]}
    with open(CALIBRACION, encoding="utf-8-sig", newline="") as f:
        humanas = {r["id"]: r["humano"].strip().lower() for r in csv.DictReader(f, delimiter=";")}
    validas = {i: h for i, h in humanas.items() if h in ("correcta", "parcial", "incorrecta")}
    if len(validas) < len(humanas):
        print(f"  aviso: {len(humanas) - len(validas)} filas sin rellenar o con un valor no válido")
    if not validas:
        sys.exit("✗ No hay correcciones válidas en el CSV")
    coinciden = [i for i, h in validas.items() if nota(juez[i]) == h]
    print(f"\nAcuerdo juez-humano: {len(coinciden)}/{len(validas)} ({len(coinciden) / len(validas):.0%})")
    for i, h in sorted(validas.items()):
        if nota(juez[i]) != h:
            print(f"  {i}: humano {h}, juez {nota(juez[i])} — {juez[i]['justificacion']}")


def rejuzgar(filas: list[dict], cliente: genai.Client, modelo: str) -> None:
    """Vuelve a pasar por el juez las respuestas ya generadas, sin generarlas de nuevo.

    Sirve para probar cambios en la rúbrica del juez sobre las MISMAS respuestas que se
    corrigieron a mano. Los fragmentos se reconstruyen con el buscador, que es
    determinista: se comprueba que salen los mismos que en la evaluación original.
    """
    buscador = Buscador()
    con = [f for f in filas if f["fuentes"]]
    for i, f in enumerate(con, start=1):
        resultados = buscador.buscar(f["pregunta"], k=5)
        if [r["id"] for r in resultados] != f["recuperados"]:
            sys.exit(f"✗ {f['id']}: el buscador ya no devuelve los mismos fragmentos (¿índice cambiado?)")
        r = {"respuesta": f["respuesta"], "contexto": contexto(resultados)}
        q = {"pregunta": f["pregunta"], "respuesta": f["referencia"]}
        antes = f["correccion"]
        veredicto, modelo_juez = juzgar(cliente, modelo, q, r)
        f.update(veredicto.model_dump())
        f["modelo_juez"] = modelo_juez
        cambio = f"  (antes {antes})" if f["correccion"] != antes else ""
        print(f"  [{i}/{len(con)}] {f['id']} {f['correccion']}{cambio}")
        time.sleep(PAUSA)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    parser = argparse.ArgumentParser(description="Evalúa las respuestas del RAG.")
    parser.add_argument("--modelo", default=MODELO_LLM, help=f"modelo de Gemini (por defecto {MODELO_LLM})")
    parser.add_argument("--de-nuevo", action="store_true", help="ignorar el progreso guardado")
    parser.add_argument("--calibracion", action="store_true", help="crear eval/calibracion.csv")
    parser.add_argument("--acuerdo", action="store_true", help="medir el acuerdo juez-humano")
    parser.add_argument("--rejuzgar", action="store_true",
                        help="volver a juzgar las respuestas guardadas (tras cambiar la rúbrica)")
    args = parser.parse_args()

    ruta = RESULTADOS / f"generacion_{args.modelo}.json"
    guardado = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() and not args.de_nuevo else {}
    filas = guardado.get("detalle", [])

    if args.calibracion or args.acuerdo:
        if not filas:
            sys.exit(f"✗ Primero hay que evaluar: no existe {ruta.relative_to(RAIZ)}")
        crear_calibracion(filas) if args.calibracion else acuerdo(filas)
        return

    if args.rejuzgar:
        if not filas:
            sys.exit(f"✗ Primero hay que evaluar: no existe {ruta.relative_to(RAIZ)}")
        rejuzgar(filas, genai.Client(), args.modelo)
        pendientes = []
    else:
        preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
        hechas = {f["id"] for f in filas}
        pendientes = [q for q in preguntas if q["id"] not in hechas]
        print(f"{len(hechas)} preguntas ya evaluadas, {len(pendientes)} pendientes")
        buscador, cliente = Buscador(), genai.Client()

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    for i, q in enumerate(pendientes, start=1):
        filas.append(evaluar_una(q, buscador, cliente, args.modelo))
        print(f"  [{i}/{len(pendientes)}] {q['id']} {filas[-1].get('correccion', 'abstención ' + str(filas[-1]['abstencion_correcta']))}")
        ruta.write_text(json.dumps({"detalle": filas}, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(PAUSA)

    filas.sort(key=lambda f: f["id"])
    metricas = resumen(filas)
    imprimir(metricas, args.modelo)
    ruta.write_text(json.dumps({
        "configuracion": {"modelo": args.modelo, "juez": args.modelo, "fecha": date.today().isoformat(),
                          "k": 5, "n_preguntas": len(filas)},
        "metricas": metricas, "detalle": filas}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {ruta.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
