"""Tool de cálculo de saldo de franquicia tributaria SENCE."""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

UTM_DEFAULT = 67000.0
TOPE_UTM = 4.5
TASA_FRANQUICIA = 0.06


def _utm_valor() -> float:
    try:
        return float(os.getenv("UTM_VALOR", str(UTM_DEFAULT)))
    except (TypeError, ValueError):
        return UTM_DEFAULT


def _cliente_supabase():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or ""
    ).strip()
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception:
        return None


def _remuneracion(trabajador) -> float:
    try:
        return float((trabajador or {}).get("remuneracion", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def calcular_saldo_franquicia(rut_empresa, trabajadores) -> dict:
    """
    Calcula la franquicia tributaria anual SENCE y el saldo disponible.

    Parámetros:
      - rut_empresa (str): RUT de la empresa.
      - trabajadores (list[dict]): cada uno con clave 'remuneracion' (CLP).
        Por compatibilidad, si se recibe un int se interpreta como cantidad
        de trabajadores sin masa imponible.

    Fórmula:
      franquicia_anual = min(masa_imponible * 6%, 4.5 * UTM_VALOR)

    El tope de 4,5 UTM es ANUAL POR EMPRESA (no por trabajador). Si existe un
    registro en `franquicia_empresas`, se usa como fuente oficial
    (franquicia_anual, usado y disponible). Si no existe, se entrega una
    estimación y se marca `es_estimacion = True`.
    """
    rut = (rut_empresa or "").strip()
    if not rut:
        return {"error": "RUT de empresa requerido"}

    if isinstance(trabajadores, int):
        cantidad = trabajadores
        masa_imponible = 0.0
    else:
        lista = trabajadores or []
        cantidad = len(lista)
        masa_imponible = sum(_remuneracion(t) for t in lista)

    utm = _utm_valor()
    tope_anual = TOPE_UTM * utm
    franquicia_anual = min(masa_imponible * TASA_FRANQUICIA, tope_anual)

    registro = None
    cliente = _cliente_supabase()
    if cliente is not None:
        try:
            respuesta = (
                cliente.table("franquicia_empresas")
                .select("*")
                .eq("rut_empresa", rut)
                .limit(1)
                .execute()
            )
            if respuesta.data:
                registro = respuesta.data[0]
        except Exception:
            registro = None

    if registro:
        franquicia_anual = float(registro.get("franquicia_anual") or franquicia_anual)
        usado = float(registro.get("usado") or 0)
        disponible = registro.get("disponible")
        disponible = (
            float(disponible)
            if disponible is not None
            else max(franquicia_anual - usado, 0)
        )
        anio = registro.get("año") or datetime.now().year
        razon_social = registro.get("razon_social") or "Desconocida"
        fuente = "franquicia_empresas"
        es_estimacion = False
        nota = "Registro oficial encontrado en franquicia_empresas."
    else:
        usado = 0.0
        disponible = max(franquicia_anual - usado, 0)
        anio = datetime.now().year
        razon_social = "Desconocida"
        fuente = "estimacion"
        es_estimacion = True
        nota = (
            "No hay registro en franquicia_empresas para este RUT; se entrega "
            "una estimación con 6% de la masa imponible y tope anual de 4,5 UTM "
            "por empresa."
        )

    return {
        "rut_empresa": rut,
        "rut": rut,
        "razon_social": razon_social,
        "trabajadores": cantidad,
        "masa_imponible": round(masa_imponible, 0),
        "utm_valor": round(utm, 0),
        "tope_anual": round(tope_anual, 0),
        "franquicia_anual": round(franquicia_anual, 0),
        "usado": round(usado, 0),
        "disponible": round(disponible, 0),
        "año": anio,
        "fuente": fuente,
        "es_estimacion": es_estimacion,
        "nota": nota,
    }
