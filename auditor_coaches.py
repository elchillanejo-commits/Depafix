#!/usr/bin/env python3
"""Auditoría de conocimiento: los Profesores Supervisores validan a los Coaches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_ENV = BASE_DIR / ".env"
CARPETA_PROFESORES = BASE_DIR / "profesores"
CONOCIMIENTO = Path("/home/ibar/Documentos/Conocimiento")

MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
MODELO_LLM = "deepseek-v4-pro"
DIMENSIONES = 384
TAMANO_FRAGMENTO = 1000
SOLAPE = 200
MINIMO_FRAGMENTO = 100
LOTE_AUDITORIA = 10
LOTE_CONSULTA = 50
LOTE_INSERCION = 25
LOTE_EMBEDDINGS = 32

EXTENSIONES = {".txt", ".md", ".pdf", ".csv", ".xlsx", ".xls", ".json"}
VEREDICTOS = {"APROBADO", "RECHAZADO", "APROBADO_CON_OBSERVACIONES"}
APROBADOS = {"APROBADO", "APROBADO_CON_OBSERVACIONES"}

FUENTES: tuple[dict[str, Any], ...] = (
    {
        "clave": "agua",
        "elemento": "agua",
        "tabla": "coach_shopify",
        "carpetas": (
            CONOCIMIENTO / "Agua_Dropshipping",
            CONOCIMIENTO / "Dropshiphing",
        ),
    },
    {
        "clave": "aire",
        "elemento": "aire",
        "tabla": "coach_pitches",
        "carpetas": (
            CONOCIMIENTO / "Ventas",
        ),
    },
    {
        "clave": "fuego",
        "elemento": "fuego",
        "tabla": "coach_python",
        "carpetas": (
            CONOCIMIENTO / "IA",
            CONOCIMIENTO / "MIcrosoft",
        ),
    },
    {
        "clave": "tierra",
        "elemento": "tierra",
        "tabla": "coach_tierra",
        "carpetas": (
            CONOCIMIENTO / "Tierra_Construccion",
            CONOCIMIENTO / "Trade",
        ),
    },
    {
        "clave": "metal",
        "elemento": "metal",
        "tabla": "coach_metal",
        "carpetas": (
            CONOCIMIENTO / "Metal_Procurador",
            CONOCIMIENTO / "Filosofia",
        ),
    },
)


def cargar_env() -> None:
    load_dotenv(ARCHIVO_ENV, override=True)


def crear_cliente() -> Any:
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        raise SystemExit(
            "Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY (o SUPABASE_KEY) en .env"
        )
    return create_client(url, key)


def crear_llm(modelo: str) -> Any:
    from langchain_openai import ChatOpenAI

    if os.getenv("OPENCODE_API_KEY", "").strip():
        return ChatOpenAI(
            model=modelo,
            temperature=0,
            api_key=os.getenv("OPENCODE_API_KEY", "").strip(),
            base_url=os.getenv(
                "OPENCODE_BASE_URL", "https://opencode.ai/inference/go/openai/v1"
            ),
            timeout=90,
            max_retries=2,
            default_headers={
                "x-opencode-session": "depafix-auditor-coaches",
                "User-Agent": "depafix-auditor/1.0",
            },
        )
    if os.getenv("OPENAI_API_KEY", "").strip():
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            timeout=90,
            max_retries=2,
        )
    if os.getenv("MOONSHOT_API_KEY", "").strip():
        return ChatOpenAI(
            model="kimi-k3.1-pro",
            temperature=0,
            api_key=os.getenv("MOONSHOT_API_KEY", "").strip(),
            base_url=os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"),
            timeout=90,
            max_retries=2,
        )
    raise SystemExit(
        "Falta OPENCODE_API_KEY, OPENAI_API_KEY o MOONSHOT_API_KEY en .env"
    )


def crear_modelo_embeddings(nombre: str) -> Any:
    from sentence_transformers import SentenceTransformer

    modelo = SentenceTransformer(nombre)
    if hasattr(modelo, "get_embedding_dimension"):
        dimension = modelo.get_embedding_dimension()
    else:
        dimension = modelo.get_sentence_embedding_dimension()
    if dimension != DIMENSIONES:
        raise SystemExit(
            f"El modelo {nombre} genera vectores de {dimension} dimensiones; "
            f"las tablas esperan {DIMENSIONES}."
        )
    return modelo


def cargar_profesor(elemento: str) -> str:
    ruta = CARPETA_PROFESORES / f"{elemento}.md"
    if not ruta.is_file():
        raise SystemExit(f"No existe el System Prompt del profesor: {ruta}")
    return ruta.read_text(encoding="utf-8", errors="replace")


def archivos_de(carpeta: Path) -> list[Path]:
    if not carpeta.is_dir():
        return []
    return sorted(
        ruta
        for ruta in carpeta.rglob("*")
        if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES
    )


def leer_archivo(ruta: Path) -> str:
    sufijo = ruta.suffix.lower()
    if sufijo in {".txt", ".md", ".json"}:
        return ruta.read_text(encoding="utf-8", errors="replace")
    if sufijo == ".pdf":
        try:
            import pdfplumber
        except ImportError as error:
            raise RuntimeError("falta pdfplumber para leer PDFs") from error
        with pdfplumber.open(ruta) as pdf:
            return "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)
    if sufijo == ".csv":
        try:
            import pandas as pd
        except ImportError as error:
            raise RuntimeError("falta pandas para leer CSV") from error
        return pd.read_csv(ruta).to_csv(index=False)
    if sufijo in {".xlsx", ".xls"}:
        try:
            import pandas as pd
        except ImportError as error:
            raise RuntimeError("falta pandas para leer Excel") from error
        try:
            hojas = pd.read_excel(ruta, sheet_name=None)
        except ImportError as error:
            raise RuntimeError("falta openpyxl para leer Excel") from error
        return "\n\n".join(hoja.to_csv(index=False) for hoja in hojas.values())
    return ""


def dividir(texto: str) -> list[str]:
    texto = texto.strip()
    if not texto:
        return []

    fragmentos: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + TAMANO_FRAGMENTO, len(texto))
        if fin < len(texto):
            corte = texto.rfind("\n", inicio + TAMANO_FRAGMENTO // 2, fin)
            if corte == -1:
                corte = texto.rfind(" ", inicio + TAMANO_FRAGMENTO // 2, fin)
            if corte != -1:
                fin = corte

        fragmento = texto[inicio:fin].strip()
        if len(fragmento) >= MINIMO_FRAGMENTO:
            fragmentos.append(fragmento)

        if fin >= len(texto):
            break
        inicio = max(fin - SOLAPE, inicio + 1)

    return fragmentos


def recolectar_fragmentos(fuente: dict[str, Any], limite: int) -> list[dict[str, Any]]:
    fragmentos: list[dict[str, Any]] = []
    for carpeta in fuente["carpetas"]:
        for ruta in archivos_de(carpeta):
            try:
                texto = leer_archivo(ruta)
            except Exception as error:
                print(f"  ERROR leyendo {ruta.name}: {type(error).__name__}: {error}")
                continue
            for contenido in dividir(texto):
                fragmentos.append(
                    {
                        "elemento": fuente["elemento"],
                        "coach": carpeta.name,
                        "fuente": ruta.name,
                        "ruta": str(ruta),
                        "contenido": contenido,
                    }
                )
                if limite and len(fragmentos) >= limite:
                    return fragmentos
    return fragmentos


def calcular_hash(elemento: str, fuente: str, contenido: str) -> str:
    base = f"{elemento}|{fuente}|{contenido}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()


def extraer_json(texto: str) -> Any:
    limpio = texto.strip()
    limpio = re.sub(r"^```(?:json)?\s*", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\s*```$", "", limpio)
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        pass
    for apertura, cierre in (("{", "}"), ("[", "]")):
        inicio = limpio.find(apertura)
        fin = limpio.rfind(cierre)
        if inicio != -1 and fin > inicio:
            try:
                return json.loads(limpio[inicio : fin + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("la respuesta del LLM no contiene JSON válido")


def normalizar_resultados(data: Any, ids: list[int]) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for clave in ("resultados", "veredictos", "aprobaciones", "results"):
            if isinstance(data.get(clave), list):
                data = data[clave]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        data = []

    por_id: dict[int, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            indice = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        por_id[indice] = item

    resultados: list[dict[str, Any]] = []
    for indice in ids:
        item = por_id.get(indice, {})
        veredicto = (
            str(item.get("veredicto", "RECHAZADO")).strip().upper().replace(" ", "_")
        )
        if veredicto not in VEREDICTOS:
            veredicto = "RECHAZADO"
        motivo = str(item.get("motivo", "")).strip()[:500]
        riesgo = str(item.get("riesgo_mezcla", "alto")).strip().lower()
        if riesgo not in {"bajo", "medio", "alto"}:
            riesgo = "alto"
        resultados.append(
            {
                "id": indice,
                "veredicto": veredicto,
                "motivo": motivo or "sin veredicto del LLM",
                "riesgo_mezcla": riesgo,
            }
        )
    return resultados


def auditar_lote(
    llm: Any, profesor: str, elemento: str, lote: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    from langchain_core.messages import HumanMessage, SystemMessage

    cargas = [
        {
            "id": indice,
            "coach": fragmento["coach"],
            "fuente": fragmento["fuente"],
            "contenido": fragmento["contenido"],
        }
        for indice, fragmento in enumerate(lote, start=1)
    ]
    instrucciones = (
        f"{profesor}\n\n"
        f"Audita el siguiente lote de {len(cargas)} fragmentos del elemento {elemento}. "
        "Evalúa cada fragmento de forma independiente: pureza del elemento, trazabilidad, "
        "duplicados, calidad, vigencia y confidencialidad. "
        "Responde EXCLUSIVAMENTE con JSON válido con esta forma: "
        '{"resultados":[{"id":1,"veredicto":"APROBADO|RECHAZADO|'
        'APROBADO_CON_OBSERVACIONES","motivo":"...","riesgo_mezcla":'
        '"bajo|medio|alto"}]}. '
        "Incluye un resultado por cada id recibido y no agregues texto fuera del JSON."
    )
    mensajes = [
        SystemMessage(content=instrucciones),
        HumanMessage(
            content=json.dumps({"fragmentos": cargas}, ensure_ascii=False)
        ),
    ]
    ids = [carga["id"] for carga in cargas]
    try:
        respuesta = llm.invoke(mensajes)
        contenido = getattr(respuesta, "content", respuesta)
        if isinstance(contenido, list):
            contenido = "".join(
                str(parte.get("text", "")) if isinstance(parte, dict) else str(parte)
                for parte in contenido
            )
        return normalizar_resultados(extraer_json(str(contenido)), ids)
    except Exception as error:
        print(f"  ERROR LLM: {type(error).__name__}: {str(error)[:200]}")
        return [
            {
                "id": indice,
                "veredicto": "RECHAZADO",
                "motivo": f"error del LLM: {type(error).__name__}",
                "riesgo_mezcla": "alto",
            }
            for indice in ids
        ]


def verificar_tabla(sb: Any, tabla: str) -> None:
    try:
        sb.table(tabla).select("id").limit(1).execute()
    except Exception as error:
        mensaje = str(error)
        if "PGRST205" in mensaje or "Could not find the table" in mensaje:
            raise SystemExit(
                f"La tabla {tabla} no existe. Ejecuta sql/coach_tables.sql en Supabase."
            ) from error
        raise


def hashes_existentes(sb: Any, tabla: str, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    try:
        respuesta = (
            sb.table(tabla).select("hash_origen").in_("hash_origen", hashes).execute()
        )
    except Exception as error:
        mensaje = str(error)
        if "hash_origen" in mensaje or "PGRST204" in mensaje:
            raise SystemExit(
                f"La tabla {tabla} no tiene hash_origen. "
                "Ejecuta sql/coach_tables.sql en Supabase."
            ) from error
        raise
    return {
        fila["hash_origen"]
        for fila in (respuesta.data or [])
        if fila.get("hash_origen")
    }


def insertar_aprobados(
    fuente: dict[str, Any],
    aprobados: list[dict[str, Any]],
    modelo: Any,
    sb: Any,
    lote_consulta: int,
) -> dict[str, int]:
    stats = {"insertados": 0, "duplicados": 0, "errores": 0}
    tabla = fuente["tabla"]
    verificar_tabla(sb, tabla)

    vistos: set[str] = set()
    unicos: list[dict[str, Any]] = []
    for fragmento in aprobados:
        fragmento["hash_origen"] = calcular_hash(
            fragmento["elemento"], fragmento["fuente"], fragmento["contenido"]
        )
        if fragmento["hash_origen"] in vistos:
            stats["duplicados"] += 1
            continue
        vistos.add(fragmento["hash_origen"])
        unicos.append(fragmento)

    pendientes: list[dict[str, Any]] = []
    for inicio in range(0, len(unicos), lote_consulta):
        lote = unicos[inicio : inicio + lote_consulta]
        existentes = hashes_existentes(
            sb, tabla, [fragmento["hash_origen"] for fragmento in lote]
        )
        for fragmento in lote:
            if fragmento["hash_origen"] in existentes:
                stats["duplicados"] += 1
            else:
                pendientes.append(fragmento)

    for inicio in range(0, len(pendientes), LOTE_INSERCION):
        lote = pendientes[inicio : inicio + LOTE_INSERCION]
        vectores = modelo.encode(
            [f"passage: {fragmento['contenido']}" for fragmento in lote],
            batch_size=LOTE_EMBEDDINGS,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        filas = [
            {
                "contenido": fragmento["contenido"],
                "metadata": {
                    "elemento": fragmento["elemento"],
                    "coach": fragmento["coach"],
                    "fuente": fragmento["fuente"],
                    "ruta": fragmento["ruta"],
                    "hash_origen": fragmento["hash_origen"],
                    "auditor": f"profesor_{fuente['elemento']}",
                    "veredicto": fragmento["veredicto"],
                    "motivo": fragmento["motivo"],
                    "riesgo_mezcla": fragmento["riesgo_mezcla"],
                },
                "embedding": vector.tolist(),
                "hash_origen": fragmento["hash_origen"],
            }
            for fragmento, vector in zip(lote, vectores)
        ]
        try:
            sb.table(tabla).insert(filas).execute()
            stats["insertados"] += len(filas)
        except Exception as error:
            stats["errores"] += len(filas)
            print(f"  ERROR insertando en {tabla}: {type(error).__name__}: {error}")
    return stats


def procesar_elemento(
    fuente: dict[str, Any],
    llm: Any,
    modelo: Any,
    sb: Any,
    args: argparse.Namespace,
) -> dict[str, int]:
    elemento = fuente["elemento"]
    profesor = cargar_profesor(elemento)
    print(f"\n[{elemento.upper()}] tabla={fuente['tabla']}")

    fragmentos = recolectar_fragmentos(fuente, args.limite)
    if not fragmentos:
        print("  Sin fragmentos para auditar.")
        return {
            "fragmentos": 0,
            "aprobados": 0,
            "rechazados": 0,
            "duplicados": 0,
            "insertados": 0,
            "errores": 0,
        }

    print(f"  Fragmentos: {len(fragmentos)} | lotes de {args.lote}")
    aprobados: list[dict[str, Any]] = []
    rechazados = 0
    total_lotes = (len(fragmentos) + args.lote - 1) // args.lote

    for numero, inicio in enumerate(range(0, len(fragmentos), args.lote), start=1):
        lote = fragmentos[inicio : inicio + args.lote]
        resultados = auditar_lote(llm, profesor, elemento, lote)
        aprobados_lote = 0
        for fragmento, resultado in zip(lote, resultados):
            fragmento["veredicto"] = resultado["veredicto"]
            fragmento["motivo"] = resultado["motivo"]
            fragmento["riesgo_mezcla"] = resultado["riesgo_mezcla"]
            if resultado["veredicto"] in APROBADOS:
                aprobados.append(fragmento)
                aprobados_lote += 1
            else:
                rechazados += 1
            if args.verbose:
                print(
                    f"    [{resultado['veredicto']}] {fragmento['fuente']} :: "
                    f"{resultado['motivo'][:120]}"
                )
        print(
            f"  Lote {numero}/{total_lotes}: "
            f"{aprobados_lote} aprobados, {len(lote) - aprobados_lote} rechazados"
        )

    stats = {
        "fragmentos": len(fragmentos),
        "aprobados": len(aprobados),
        "rechazados": rechazados,
        "duplicados": 0,
        "insertados": 0,
        "errores": 0,
    }

    if args.dry_run:
        vistos: set[str] = set()
        for fragmento in aprobados:
            huella = calcular_hash(
                fragmento["elemento"], fragmento["fuente"], fragmento["contenido"]
            )
            if huella in vistos:
                stats["duplicados"] += 1
            else:
                vistos.add(huella)
        print(
            f"  DRY-RUN: {stats['aprobados']} aprobados, {stats['rechazados']} "
            f"rechazados, {stats['duplicados']} duplicados en el lote."
        )
        return stats

    resultado_insercion = insertar_aprobados(
        fuente, aprobados, modelo, sb, LOTE_CONSULTA
    )
    stats.update(resultado_insercion)
    print(
        f"  Ingesta: {stats['insertados']} insertados, "
        f"{stats['duplicados']} duplicados omitidos, {stats['errores']} errores."
    )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audita los reportes de los Coaches con los Profesores Supervisores "
            "antes de ingestarlos en Supabase."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la auditoría y muestra veredictos sin escribir en Supabase.",
    )
    parser.add_argument(
        "--solo",
        choices=[fuente["clave"] for fuente in FUENTES],
        help="Audita solo un elemento.",
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=LOTE_AUDITORIA,
        help=f"Fragmentos por petición al LLM (por defecto: {LOTE_AUDITORIA}).",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Máximo de fragmentos por elemento (0 = sin límite).",
    )
    parser.add_argument(
        "--modelo",
        default=MODELO_EMBEDDINGS,
        help=f"Modelo de embeddings (por defecto: {MODELO_EMBEDDINGS}).",
    )
    parser.add_argument(
        "--modelo-llm",
        default=MODELO_LLM,
        help=f"Modelo auditor (por defecto: {MODELO_LLM}).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Muestra el veredicto de cada fragmento.",
    )
    args = parser.parse_args()

    if args.lote < 1:
        raise SystemExit("--lote debe ser mayor o igual a 1.")
    if args.limite < 0:
        raise SystemExit("--limite debe ser mayor o igual a 0.")

    cargar_env()
    if not CARPETA_PROFESORES.is_dir():
        raise SystemExit(f"No existe la carpeta de profesores: {CARPETA_PROFESORES}")

    fuentes = [
        fuente
        for fuente in FUENTES
        if args.solo is None or fuente["clave"] == args.solo
    ]
    for fuente in fuentes:
        cargar_profesor(fuente["elemento"])

    llm = crear_llm(args.modelo_llm)
    modelo = None
    sb = None
    if not args.dry_run:
        sb = crear_cliente()
        modelo = crear_modelo_embeddings(args.modelo)

    totales = {
        "fragmentos": 0,
        "aprobados": 0,
        "rechazados": 0,
        "duplicados": 0,
        "insertados": 0,
        "errores": 0,
    }
    for fuente in fuentes:
        try:
            stats = procesar_elemento(fuente, llm, modelo, sb, args)
        except SystemExit:
            raise
        except Exception as error:
            print(
                f"ERROR en {fuente['elemento']}: {type(error).__name__}: {error}"
            )
            totales["errores"] += 1
            continue
        for clave in totales:
            totales[clave] += stats.get(clave, 0)

    print(
        f"\nResumen: {totales['fragmentos']} fragmentos, "
        f"{totales['aprobados']} aprobados, {totales['rechazados']} rechazados, "
        f"{totales['duplicados']} duplicados, {totales['insertados']} insertados, "
        f"{totales['errores']} errores."
    )
    if args.dry_run:
        print("DRY-RUN: no se escribió nada en Supabase.")
    return 1 if totales["errores"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
