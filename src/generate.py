"""Paso 7: responde una pregunta con un LLM a partir de los chunks recuperados.

1. retrieve.py busca los k chunks más parecidos a la pregunta.
2. Se monta UN texto con los chunks numerados [1]..[k] y la pregunta, y se envía al LLM
   junto con las instrucciones (system prompt).
3. El LLM devuelve una salida estructurada (JSON): si ha encontrado la información, la
   respuesta con citas [n] y los números de los fragmentos que ha usado.

El LLM no busca nada por su cuenta ni tiene memoria entre preguntas: solo lee lo que le
mandamos. El proveedor es Gemini (nivel gratuito); la clave se lee de la variable de
entorno GEMINI_API_KEY, que se carga del archivo .env (ignorado por git).

El nivel gratuito a veces responde "alta demanda" (503) o "límite alcanzado" (429): se
reintenta con espera creciente y, si sigue fallando, se prueba con el modelo de reserva.

Uso (desde la raíz del proyecto, después de index.py):
    python src/generate.py "¿Las prácticas se cobran?"
    python src/generate.py "¿Cuántas horas al día?" --modelo gemini-3.5-flash-lite
"""
import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

from retrieve import Buscador, cita

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# En el nivel gratuito, los modelos Flash completos respondían "alta demanda" (503) de forma
# persistente; los Flash-Lite sí responden.
MODELO_LLM = "gemini-3.5-flash-lite"
MODELOS_RESERVA = ["gemini-3.1-flash-lite"]
K = 5
REINTENTOS = 3

INSTRUCCIONES = """Eres un asistente que responde dudas de estudiantes sobre la normativa de la \
Universidad de Cádiz: Trabajos Fin de Grado y Máster (TFG/TFM) y prácticas académicas externas.

Reglas:
1. Responde ÚNICAMENTE con la información de los fragmentos de normativa que se te dan. No uses \
conocimientos propios ni normativa de otras universidades, aunque creas saber la respuesta.
2. Cita cada dato con el número de su fragmento entre corchetes, por ejemplo [2].
3. Si los fragmentos no contienen la respuesta, pon "encontrado" a false y explica brevemente que \
no aparece en la normativa consultada. No intentes deducirla ni la completes con suposiciones.
4. Si la respuesta está solo en parte, responde esa parte y di claramente qué falta.
5. Hay dos reglamentos de TFG: el reglamento marco de la UCA y el reglamento de la Escuela \
Superior de Ingeniería (ESI), que lo concreta para sus titulaciones. Si los dos tratan la \
pregunta y dicen cosas distintas, explica lo que dice cada uno e indica que el de la ESI es el \
específico para sus estudiantes.
6. Las prácticas curriculares y las extracurriculares tienen reglas distintas: si la pregunta no \
dice cuáles, responde para las dos cuando difieran.
7. Responde en español, de forma clara y breve (unas pocas frases o una lista corta), dirigiéndote \
al estudiante. No copies los artículos enteros."""


class Respuesta(BaseModel):
    """Formato que debe devolver el LLM (salida estructurada)."""
    encontrado: bool = Field(description="true si los fragmentos contienen la respuesta, aunque sea en parte")
    respuesta: str = Field(description="respuesta al estudiante, con citas [n]")
    fuentes: list[int] = Field(description="números de los fragmentos usados en la respuesta")


def contexto(resultados: list[dict]) -> str:
    """Los chunks numerados [1]..[k], cada uno con su cita, para el prompt."""
    bloques = []
    for n, r in enumerate(resultados, start=1):
        cabecera = f"[{n}] {cita(r)} · {r['titulo_documento']}"
        if r["titulo"] and r["tipo"] == "articulo":
            cabecera += f" — {r['titulo']}"
        if r["modificado_por"]:
            cabecera += f" (redacción vigente tras la modificación {r['modificado_por']})"
        bloques.append(f"{cabecera}\n{r['texto']}")
    return "\n\n".join(bloques)


def llamar(cliente: genai.Client, modelos: list[str], prompt: str,
           instrucciones: str = INSTRUCCIONES, esquema: type[BaseModel] = Respuesta) -> tuple[BaseModel, str]:
    """Pide al primer modelo que funcione una salida con el esquema dado, con reintentos.

    Devuelve (salida, modelo usado). La reutiliza también el juez de evaluate_generation.py.
    """
    config = types.GenerateContentConfig(
        system_instruction=instrucciones,
        temperature=0,  # lo más estable posible: misma pregunta, misma respuesta
        response_mime_type="application/json",
        response_schema=esquema,
    )
    ultimo_error = None
    for modelo in modelos:
        for intento in range(REINTENTOS):
            try:
                r = cliente.models.generate_content(model=modelo, contents=prompt, config=config)
                return esquema.model_validate_json(r.text), modelo
            except (errors.ServerError, errors.ClientError) as error:
                # 503 = saturado, 429 = límite gratuito: merece la pena esperar y reintentar.
                if getattr(error, "code", None) not in (429, 503):
                    raise
                ultimo_error = error
                time.sleep(5 * 2 ** intento)  # 5 s, 10 s, 20 s
    raise RuntimeError(f"Ningún modelo ha respondido: {ultimo_error}")


def responder(pregunta: str, buscador: Buscador, cliente: genai.Client,
              modelo: str = MODELO_LLM, k: int = K) -> dict:
    """Busca los chunks, pregunta al LLM y devuelve la respuesta con sus fuentes."""
    resultados = buscador.buscar(pregunta, k=k)
    fragmentos = contexto(resultados)
    prompt = f"Fragmentos de normativa:\n\n{fragmentos}\n\nPregunta del estudiante: {pregunta}"
    salida, modelo_usado = llamar(cliente, [modelo] + [m for m in MODELOS_RESERVA if m != modelo], prompt)

    # Solo se aceptan números de fragmento que existan (el LLM podría inventarse un [7]).
    usadas = [n for n in dict.fromkeys(salida.fuentes) if 1 <= n <= len(resultados)]
    return {"pregunta": pregunta, "encontrado": salida.encontrado, "respuesta": salida.respuesta,
            "modelo": modelo_usado,
            "fuentes": [{"n": n, "id": resultados[n - 1]["id"], "unidad": resultados[n - 1]["unidad"],
                         "cita": cita(resultados[n - 1]), "url": resultados[n - 1]["url"]}
                        for n in usadas],
            "recuperados": [r["id"] for r in resultados],
            "contexto": fragmentos}  # lo que leyó el LLM (lo necesita el juez para medir la fidelidad)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows
    parser = argparse.ArgumentParser(description="Responde una pregunta sobre la normativa.")
    parser.add_argument("pregunta")
    parser.add_argument("--modelo", default=MODELO_LLM, help=f"modelo de Gemini (por defecto {MODELO_LLM})")
    parser.add_argument("-k", type=int, default=K, help=f"chunks que se pasan al LLM (por defecto {K})")
    args = parser.parse_args()

    resultado = responder(args.pregunta, Buscador(), genai.Client(), args.modelo, args.k)
    print(f"\n{resultado['respuesta']}\n")
    for f in resultado["fuentes"]:
        print(f"  [{f['n']}] {f['cita']}")
    if not resultado["encontrado"]:
        print("  (no encontrado en la normativa)")
    print(f"\n  modelo: {resultado['modelo']}")


if __name__ == "__main__":
    main()
