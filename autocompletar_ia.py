from __future__ import annotations

import json
import os
import random
import re
import shutil
import time
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI

BASE_DIR = Path(__file__).resolve().parent
TSV_PATH = BASE_DIR / "datos" / "prospectos_300.tsv"
CSV_PATH = BASE_DIR / "datos" / "lista_final.csv"

BATCH_SIZE = 5
SLEEP_ENTRE_LLAMADAS = 2.0
SLEEP_ENTRE_LOTES = 5.0
MAX_REINTENTOS_API = 4
MAX_INTENTOS_JSON = 2
ENEATIPO_RE = re.compile(r"\b([1-9])\s*w\s*([1-9])\b", re.IGNORECASE)

CAMPOS_CONTEXTO = (
    "Rubro",
    "Vínculo",
    "Rol",
    "Info_clave",
    "Speech_clave",
    "Últ_contacto",
    "Próx_acción",
    "Fecha_próx",
    "Edad",
    "Conozco_desde",
    "Ultima_charla",
    "Frecuencia",
    "Cercania",
    "Confianza",
    "Base_relacion",
    "Nivel_Tenis",
    "Red_Contactos",
    "Estado_civil",
    "Hijos",
    "Vive_en",
    "Economia",
    "Problemas",
    "Logros",
    "Le_importa",
    "Le_molesta",
    "Como_decide",
    "Riesgo",
    "Conoce_gente_plata",
    "Circulos",
    "Red_util",
    "Presenta_gente",
    "Le_pedi_algo",
    "Me_pidio_algo",
    "Pendientes",
    "NO_decir",
    "SI_decir",
)

SYSTEM_PROMPT = (
    "Eres un analista experto en Eneagrama, psicología de ventas y comunicación. "
    "Trabajas para un corredor de departamentos en Carmen Mena 1050 que se mueve en la red "
    "del Club Stade Français. Completa la ficha de un prospecto con rol de PAR: cercano, "
    "directo, sin presión y sin vender directamente. "
    "El Eneatipo debe incluir ala y usar formato 5w6 (tipo base 1-9 y ala distinta). "
    "El Arquetipo debe ser breve. El diagnóstico debe ser psicológico, accionable y de "
    "máximo 2 frases. El speech debe ser un mensaje de WhatsApp de máximo 3 líneas, "
    "personalizado, usando tenis o café como excusa si falta contexto. No uses emojis. "
    "No menciones departamentos, precios, inversión, rentabilidad ni disponibilidad. "
    "Si hay Eneatipo o Arquetipo existentes, respétalos. Responde SOLO con JSON válido."
)

load_dotenv(BASE_DIR / ".env")


def es_vacio(valor: Any) -> bool:
    return str(valor).strip().lower() in {"", "?", "nan", "none", "null"}


def cargar_df() -> pd.DataFrame:
    if not TSV_PATH.exists():
        raise FileNotFoundError(f"No existe {TSV_PATH}")
    df = pd.read_csv(TSV_PATH, sep="\t", dtype=str, keep_default_na=False)
    requeridas = ["Nombre", "Eneatipo", "Arquetipo", "Porque", "Speech", "Estado"]
    faltantes = [columna for columna in requeridas if columna not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en {TSV_PATH}: {faltantes}")
    return df


def crear_cliente() -> OpenAI:
    api_key = os.getenv("MOONSHOT_API_KEY", "").strip()
    base_url = os.getenv("MOONSHOT_BASE_URL", "").strip().rstrip("/")
    if not api_key:
        raise ValueError("Falta MOONSHOT_API_KEY en .env")
    if not base_url:
        raise ValueError("Falta MOONSHOT_BASE_URL en .env")
    return OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)


def obtener_modelo() -> str:
    modelo = os.getenv("MOONSHOT_MODEL", "").strip()
    if modelo:
        return modelo
    base_url = os.getenv("MOONSHOT_BASE_URL", "").lower()
    return "deepseek-chat" if "deepseek" in base_url else "kimi-k3.1-pro"


def construir_contexto(row: pd.Series) -> str:
    lineas = []
    for campo in CAMPOS_CONTEXTO:
        valor = str(row.get(campo, "")).strip()
        if not es_vacio(valor):
            valor = " ".join(valor.split())
            lineas.append(f"- {campo}: {valor[:250]}")
    return "\n".join(lineas)


def construir_prompt(row: pd.Series, solo_nombre: bool) -> str:
    nombre = str(row.get("Nombre", "")).strip()
    contexto = construir_contexto(row)
    eneatipo = str(row.get("Eneatipo", "")).strip()
    arquetipo = str(row.get("Arquetipo", "")).strip()

    partes = ["Prospecto a analizar:", f"- Nombre: {nombre}"]
    if contexto:
        partes.append(contexto)

    if not es_vacio(eneatipo) or not es_vacio(arquetipo):
        partes.append("\nDatos ya definidos que debes respetar:")
        if not es_vacio(eneatipo):
            partes.append(f"- Eneatipo: {eneatipo}")
        if not es_vacio(arquetipo):
            partes.append(f"- Arquetipo: {arquetipo}")

    if solo_nombre:
        partes.append(
            "\nNo hay más información disponible. Asume que es un contacto del Club Stade "
            "(tenis) y genera un perfil base plausible. El diagnóstico debe ser una hipótesis "
            "inicial, no un hecho."
        )

    partes.append(
        "\nDevuelve SOLO un objeto JSON válido, sin markdown ni texto adicional, con esta forma:\n"
        '{"eneatipo": "5w6", "arquetipo": "Descartes", "diagnostico": "...", "speech": "..."}'
    )
    return "\n".join(partes)


def parsear_json(texto: str) -> dict[str, Any]:
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```(?:json)?\s*", "", limpio, flags=re.IGNORECASE)
        limpio = re.sub(r"\s*```$", "", limpio)
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio == -1 or fin == -1 or fin <= inicio:
        raise ValueError("La respuesta no contiene un objeto JSON")
    data = json.loads(limpio[inicio : fin + 1])
    if not isinstance(data, dict):
        raise ValueError("La respuesta JSON no es un objeto")
    return data


def obtener_valor(data: dict[str, Any], *claves: str) -> str:
    normalizado = {str(clave).strip().lower(): valor for clave, valor in data.items()}
    for clave in claves:
        if clave.lower() in normalizado:
            return str(normalizado[clave.lower()]).strip()
    return ""


def normalizar_eneatipo(valor: Any) -> str | None:
    match = ENEATIPO_RE.search(str(valor))
    if not match:
        return None
    base, ala = match.groups()
    if base == ala:
        return None
    return f"{base}w{ala}"


def normalizar_diagnostico(valor: Any) -> str:
    return " ".join(str(valor).replace("\t", " ").split()).strip()


def normalizar_speech(valor: Any) -> str:
    texto = str(valor).replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lineas = [" ".join(line.split()) for line in texto.split("\n") if line.strip()]
    return "\n".join(lineas[:3]).strip()


def normalizar_resultado(data: dict[str, Any], row: pd.Series) -> dict[str, str]:
    eneatipo_existente = str(row.get("Eneatipo", "")).strip()
    arquetipo_existente = str(row.get("Arquetipo", "")).strip()

    eneatipo_ia = normalizar_eneatipo(obtener_valor(data, "eneatipo", "enneatype"))
    arquetipo_ia = " ".join(obtener_valor(data, "arquetipo", "archetype").split())
    diagnostico = normalizar_diagnostico(
        obtener_valor(data, "diagnostico", "diagnóstico")
    )
    speech = normalizar_speech(obtener_valor(data, "speech", "mensaje", "whatsapp"))

    eneatipo = eneatipo_existente if not es_vacio(eneatipo_existente) else eneatipo_ia
    arquetipo = arquetipo_existente if not es_vacio(arquetipo_existente) else arquetipo_ia

    if es_vacio(eneatipo):
        raise ValueError("Eneatipo vacío o inválido")
    if es_vacio(arquetipo):
        raise ValueError("Arquetipo vacío")
    if not diagnostico:
        raise ValueError("Diagnóstico vacío")
    if not speech:
        raise ValueError("Speech vacío")

    return {
        "eneatipo": eneatipo,
        "arquetipo": arquetipo,
        "diagnostico": diagnostico,
        "speech": speech,
    }


def llamar_api(client: OpenAI, prompt: str) -> str:
    modelo = obtener_modelo()
    ultimo_error: Exception | None = None

    for intento in range(1, MAX_REINTENTOS_API + 1):
        try:
            respuesta = client.chat.completions.create(
                model=modelo,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=1.0,
                max_tokens=4000,
            )
            return (respuesta.choices[0].message.content or "").strip()
        except Exception as exc:
            ultimo_error = exc
            status = getattr(exc, "status_code", None)
            transitorio = status in {429, 500, 502, 503, 504} or isinstance(
                exc, (APITimeoutError, APIConnectionError)
            )
            if not transitorio or intento == MAX_REINTENTOS_API:
                raise
            espera = min(30.0, 2.0**intento) + random.uniform(0, 1)
            print(
                f"  Error transitorio ({status or type(exc).__name__}). "
                f"Reintento {intento}/{MAX_REINTENTOS_API} en {espera:.1f}s..."
            )
            time.sleep(espera)

    raise RuntimeError(f"API falló: {ultimo_error}")


def analizar_prospecto(
    client: OpenAI, row: pd.Series, solo_nombre: bool
) -> dict[str, str]:
    prompt = construir_prompt(row, solo_nombre)
    ultimo_error: Exception | None = None

    for intento in range(1, MAX_INTENTOS_JSON + 1):
        try:
            texto = llamar_api(client, prompt)
            data = parsear_json(texto)
            return normalizar_resultado(data, row)
        except ValueError as exc:
            ultimo_error = exc
            if intento == MAX_INTENTOS_JSON:
                break
            print(f"  Respuesta inválida ({exc}). Reintentando formato...")
            prompt += (
                "\n\nCORRECCIÓN: tu respuesta anterior no cumplió el formato. "
                "Devuelve SOLO JSON válido con las cuatro claves exactas: "
                "eneatipo, arquetipo, diagnostico, speech."
            )

    raise ValueError(f"No se pudo obtener un análisis válido: {ultimo_error}")


def aplicar_resultado(
    df: pd.DataFrame, idx: Any, resultado: dict[str, str], solo_nombre: bool
) -> list[str]:
    cambios = []
    for columna, clave in (
        ("Eneatipo", "eneatipo"),
        ("Arquetipo", "arquetipo"),
        ("Porque", "diagnostico"),
        ("Speech", "speech"),
    ):
        if es_vacio(df.at[idx, columna]):
            df.at[idx, columna] = resultado[clave]
            cambios.append(columna)
    if solo_nombre:
        df.at[idx, "Estado"] = "inferido_ia"
        cambios.append("Estado")
    return cambios


def guardar_tsv(df: pd.DataFrame) -> None:
    tmp = TSV_PATH.with_name(TSV_PATH.name + ".tmp")
    df.to_csv(tmp, sep="\t", index=False, encoding="utf-8", lineterminator="\n")
    tmp.replace(TSV_PATH)


def guardar_csv(df: pd.DataFrame) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CSV_PATH.with_name(CSV_PATH.name + ".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8", lineterminator="\n")
    tmp.replace(CSV_PATH)


def crear_backup() -> None:
    backup = TSV_PATH.with_name(TSV_PATH.name + ".bak")
    if not backup.exists():
        shutil.copy2(TSV_PATH, backup)
        print(f"Backup creado: {backup}")


def main() -> int:
    print("Autocompletar IA - DepaFix Maestro")
    print(f"TSV: {TSV_PATH}")

    try:
        client = crear_cliente()
        df = cargar_df()
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Modelo: {obtener_modelo()}")
    print(f"Base URL: {os.getenv('MOONSHOT_BASE_URL', '').strip()}")

    mask_eneatipo = df["Eneatipo"].map(es_vacio)
    mask_porque = df["Porque"].map(es_vacio)
    mask_speech = df["Speech"].map(es_vacio)
    mask = mask_eneatipo | mask_porque | mask_speech
    indices = list(df.index[mask])

    total = len(indices)
    total_sin_eneatipo = int(mask_eneatipo.sum())
    total_con_eneatipo = total - total_sin_eneatipo

    print(f"Prospectos a completar: {total}")
    print(f"  - Sin Eneatipo (perfil inferido): {total_sin_eneatipo}")
    print(f"  - Con Eneatipo, faltan Porque/Speech: {total_con_eneatipo}")

    if total == 0:
        guardar_csv(df)
        print("No hay prospectos pendientes. CSV sincronizado.")
        return 0

    crear_backup()
    completados = 0
    errores = 0
    total_lotes = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for numero_lote, inicio in enumerate(range(0, total, BATCH_SIZE), start=1):
        lote = indices[inicio : inicio + BATCH_SIZE]
        print(f"\nLote {numero_lote}/{total_lotes}")

        for idx in lote:
            row = df.loc[idx]
            nombre = str(row.get("Nombre", "")).strip() or f"fila {idx}"
            solo_nombre = not any(
                not es_vacio(row.get(campo, "")) for campo in CAMPOS_CONTEXTO
            )
            print(f"Analizando: {nombre}")

            try:
                resultado = analizar_prospecto(client, row, solo_nombre)
                cambios = aplicar_resultado(df, idx, resultado, solo_nombre)
                completados += 1
                print(
                    f"Prospecto {completados}/{total} completado: {nombre} "
                    f"-> {df.at[idx, 'Eneatipo']} / {df.at[idx, 'Arquetipo']} "
                    f"({', '.join(cambios)})"
                )
            except Exception as exc:
                errores += 1
                print(f"ERROR con {nombre}: {exc}")

            time.sleep(SLEEP_ENTRE_LLAMADAS)

        guardar_tsv(df)
        print(f"Progreso guardado: {completados}/{total} en {TSV_PATH}")

        if inicio + BATCH_SIZE < total:
            time.sleep(SLEEP_ENTRE_LOTES)

    guardar_csv(df)
    print(f"\nTSV actualizado: {TSV_PATH}")
    print(f"CSV actualizado: {CSV_PATH}")
    print(f"Resultado final: {completados} completados, {errores} errores.")
    if errores:
        print("Quedaron prospectos pendientes. Ejecuta de nuevo para reintentarlos.")
    return 0 if errores == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
