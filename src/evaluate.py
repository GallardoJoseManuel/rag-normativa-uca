"""Paso 6: mide el buscador con el conjunto de evaluación (eval/questions.json).

Pasa cada pregunta por el buscador de retrieve.py (el mismo que usarán los usuarios),
compara los chunks recuperados con las fuentes de la pregunta y calcula:

- Acierto@k: ¿hay al menos una fuente correcta entre los k primeros chunks?
- Recall@k:  ¿qué fracción de las fuentes de la pregunta está entre los k primeros?
- MRR:       media de 1 / posición de la primera fuente correcta (0 si no sale en el top 10).

Un chunk es correcto si su artículo (el id sin _p1, _p2...) está entre las fuentes. Las
preguntas sin fuentes ("sin_respuesta") no entran en las métricas; de ellas se compara la
similitud máxima con la de las demás, para ver si el buscador "nota" que no hay respuesta.

Muestra las métricas en total y por tipo de pregunta, lista los fallos (ninguna fuente en
el top 5) y guarda todo, con la configuración, en eval/resultados/<colección>.json, que
es la referencia para comparar los experimentos del paso 8.

Uso (desde la raíz del proyecto, después de index.py):
    python src/evaluate.py
    python src/evaluate.py --modelo intfloat/multilingual-e5-small
    python src/evaluate.py --etiqueta A_encabezado   # experimento del paso 8
"""
import argparse
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from index import MODELO, nombre_coleccion
from retrieve import RESERVA_MARCO, Buscador

RAIZ = Path(__file__).resolve().parent.parent
PREGUNTAS = RAIZ / "eval" / "questions.json"
RESULTADOS = RAIZ / "eval" / "resultados"

KS = (1, 3, 5, 10)
K_FALLO = 5  # una pregunta "falla" si no hay ninguna fuente correcta en el top 5


def puntuar(recuperados: list[str], fuentes: list[str]) -> dict:
    """Métricas de una pregunta a partir de las unidades recuperadas, en orden."""
    fuentes = set(fuentes)
    metricas = {}
    for k in KS:
        encontradas = set(recuperados[:k]) & fuentes
        metricas[f"acierto@{k}"] = 1.0 if encontradas else 0.0
        metricas[f"recall@{k}"] = len(encontradas) / len(fuentes)
    posicion = next((i for i, u in enumerate(recuperados, start=1) if u in fuentes), None)
    metricas["rr"] = 1 / posicion if posicion else 0.0  # rango recíproco; su media es el MRR
    metricas["posicion"] = posicion
    return metricas


def media(filas: list[dict]) -> dict:
    """Media de cada métrica sobre un grupo de preguntas."""
    claves = [f"{m}@{k}" for m in ("acierto", "recall") for k in KS] + ["rr"]
    resultado = {c: statistics.mean(f[c] for f in filas) for c in claves}
    resultado["mrr"] = resultado.pop("rr")
    resultado["n"] = len(filas)
    return resultado


def tabla(grupos: dict[str, dict]) -> str:
    cab = f"{'':<14}{'n':>3}" + "".join(f"{'Acierto@' + str(k):>11}" for k in KS) \
          + f"{'Recall@5':>10}{'MRR':>7}"
    filas = [cab]
    for nombre, m in grupos.items():
        filas.append(f"{nombre:<14}{m['n']:>3}"
                     + "".join(f"{m[f'acierto@{k}']:>11.0%}" for k in KS)
                     + f"{m['recall@5']:>10.0%}{m['mrr']:>7.2f}")
    return "\n".join(filas)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    parser = argparse.ArgumentParser(description="Evalúa el buscador con eval/questions.json.")
    parser.add_argument("--modelo", default=MODELO, help=f"colección a evaluar (por defecto {MODELO})")
    parser.add_argument("--reserva-marco", type=int, default=RESERVA_MARCO,
                        help="puestos del top 5 reservados al reglamento marco (experimento B)")
    parser.add_argument("--etiqueta", default="",
                        help="nombre del experimento: guarda en <colección>__<etiqueta>.json "
                             "sin pisar la línea base")
    args = parser.parse_args()

    preguntas = json.loads(PREGUNTAS.read_text(encoding="utf-8"))
    buscador = Buscador(args.modelo, args.reserva_marco)

    detalle, inicio = [], time.perf_counter()
    for q in preguntas:
        resultados = buscador.buscar(q["pregunta"], k=max(KS))
        fila = {"id": q["id"], "tipo": q["tipo"], "pregunta": q["pregunta"],
                "fuentes": q["fuentes"], "similitud_max": resultados[0]["similitud"],
                "recuperados": [[r["id"], round(r["similitud"], 4)] for r in resultados]}
        if q["fuentes"]:
            fila.update(puntuar([r["unidad"] for r in resultados], q["fuentes"]))
        detalle.append(fila)
    segundos = (time.perf_counter() - inicio) / len(preguntas)

    con_fuentes = [f for f in detalle if f["fuentes"]]
    grupos = {"TOTAL": media(con_fuentes)}
    for tipo in sorted({f["tipo"] for f in con_fuentes}):
        grupos[tipo] = media([f for f in con_fuentes if f["tipo"] == tipo])

    print(f"\nModelo {buscador.nombre_modelo} · {len(con_fuentes)} preguntas con fuentes · "
          f"{segundos * 1000:.0f} ms por pregunta\n")
    print(tabla(grupos))

    sin = [f["similitud_max"] for f in detalle if not f["fuentes"]]
    con = [f["similitud_max"] for f in con_fuentes]
    print(f"\nSimilitud del 1.er resultado: con respuesta mediana {statistics.median(con):.3f} "
          f"(mín. {min(con):.3f}); sin respuesta mediana {statistics.median(sin):.3f} "
          f"(máx. {max(sin):.3f})")

    fallos = [f for f in con_fuentes if not f[f"acierto@{K_FALLO}"]]
    print(f"\nFallos (ninguna fuente en el top {K_FALLO}): {len(fallos)}")
    for f in fallos:
        print(f"\n  {f['id']} ({f['tipo']}) {f['pregunta']}")
        print(f"    fuentes:   {', '.join(f['fuentes'])}"
              + (f"  (primera correcta en la posición {f['posicion']})" if f["posicion"] else ""))
        print(f"    top 3:     " + ", ".join(f"{i} ({s:.3f})" for i, s in f["recuperados"][:3]))
    incompletas = [f for f in con_fuentes if len(f["fuentes"]) > 1 and f["acierto@5"] and f["recall@5"] < 1]
    print(f"\nPreguntas con varias fuentes en las que falta alguna en el top 5: "
          f"{', '.join(f['id'] for f in incompletas) or 'ninguna'}")

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    sufijo = f"__{args.etiqueta}" if args.etiqueta else ""
    ruta = RESULTADOS / f"{nombre_coleccion(args.modelo)}{sufijo}.json"
    ruta.write_text(json.dumps({
        "configuracion": {"modelo": buscador.nombre_modelo, "coleccion": buscador.coleccion.name,
                          "etiqueta": args.etiqueta or "linea_base",
                          "reserva_marco": args.reserva_marco,
                          "fecha": date.today().isoformat(), "ks": KS,
                          "n_preguntas": len(preguntas), "ms_por_pregunta": round(segundos * 1000)},
        "metricas": grupos, "detalle": detalle}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {ruta.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
