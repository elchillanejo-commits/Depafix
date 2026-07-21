"""
report_generator.py -- reportes periodicos (horario/diario/semanal/
quincenal/mensual) y alertas en tiempo real para el sistema de trading.

Arquitectura: sin scheduler propio. trading_orchestrator.py corre en modo
batch cada ~5 min via Railway Cron (ver su docstring) -- este modulo
aprovecha ese mismo ciclo como "tick": generar_reportes_vencidos() consulta
en reportes_trading cuando fue la ultima corrida de cada tipo y genera los
que ya vencieron. Deliberadamente NO usa un archivo local (last_report.json)
para guardar el ultimo timestamp: el worker es un proceso batch que termina
y se relanza en cada corrida (ver Dockerfile.worker), asi que cualquier
estado en disco local se pierde entre corridas. El estado vive en Supabase
(la propia tabla reportes_trading), que sobrevive al reinicio del
contenedor.

Fuentes de datos para los reportes:
  - operaciones_ejecutadas: señales COMPRA/VENTA reales (esa tabla nunca
    guarda ESPERA -- ver TradingOrchestrator.procesar_activo, que solo
    audita señales accionables).
  - salud_agentes: cada ciclo deja activos_analizados y señales_detectadas
    en metricas (ver core/salud_agentes.py y
    TradingOrchestrator._ejecutar_ciclo_con_salud). ESPERA se estima como
    activos_analizados - señales_detectadas sumado en el periodo -- no
    existe una tabla que guarde cada ESPERA individual (séria ~6x más
    escritura por ciclo para un dato ya derivable de lo que se audita).

Alertas: enviar_alerta() siempre loguea. Si TELEGRAM_BOT_TOKEN y
TELEGRAM_CHAT_ID están configurados (variables de entorno), también envía
el mensaje por Telegram. Sin esas variables, el sistema sigue funcionando
solo con logs -- Telegram es un canal adicional, no una dependencia dura.

Uso manual (fuera del ciclo normal, para probar):
    python3 -m src.trading.report_generator --tipo diario
"""
import json
import logging
import os
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

CORE_PATH = Path("/home/ibar/Proyectos/02_PROCURADOR")  # reorg 2026-07-19: core/ movido fuera de DepaFix
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.resiliencia import red_segura, RedFailSafeError

logger = logging.getLogger(__name__)

TABLA_REPORTES = "reportes_trading"
TABLA_OPERACIONES = "operaciones_ejecutadas"
TABLA_SALUD = "salud_agentes"
NOMBRE_PROCESO = "trading_orchestrator"

# Ventana de cada tipo de reporte, en horas. "quincenal"/"mensual" son
# aproximados (14d/30d fijos, no meses calendario) para no sumar una
# dependencia (python-dateutil) solo por esto.
VENTANAS_REPORTE_HORAS = {
    "horario": 1,
    "diario": 24,
    "semanal": 24 * 7,
    "quincenal": 24 * 14,
    "mensual": 24 * 30,
}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_TIMEOUT_SEG = 5.0


def enviar_alerta(mensaje: str, nivel: str = "INFO") -> None:
    """Notifica un evento relevante (señal COMPRA/VENTA, error crítico,
    tendencia detectada...). Siempre loguea. Si hay credenciales de
    Telegram, también envía el mensaje ahí. Nunca lanza: una alerta que
    falla no debe tumbar el ciclo que la disparó."""
    nivel = nivel.upper()
    log_fn = {"CRITICAL": logger.critical, "WARNING": logger.warning}.get(nivel, logger.info)
    log_fn("ALERTA [%s]: %s", nivel, mensaje)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = httpx.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": f"[{nivel}] {mensaje}"},
                           timeout=TELEGRAM_TIMEOUT_SEG)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("No se pudo enviar la alerta por Telegram (queda solo en el log): %s", e)


@red_segura()
def _fetch_operaciones(cliente, desde: datetime, hasta: datetime) -> List[Dict[str, Any]]:
    resp = (
        cliente.table(TABLA_OPERACIONES)
        .select("*")
        .gte("timestamp", desde.isoformat())
        .lt("timestamp", hasta.isoformat())
        .execute()
    )
    return resp.data or []


@red_segura()
def _fetch_salud(cliente, desde: datetime, hasta: datetime) -> List[Dict[str, Any]]:
    resp = (
        cliente.table(TABLA_SALUD)
        .select("metricas")
        .eq("proceso", NOMBRE_PROCESO)
        .gte("corrido_at", desde.isoformat())
        .lt("corrido_at", hasta.isoformat())
        .execute()
    )
    return resp.data or []


def generar_resumen(cliente, desde: datetime, hasta: datetime) -> Dict[str, Any]:
    """Estadísticas de señales en [desde, hasta): cantidad de COMPRA/VENTA
    (reales, de operaciones_ejecutadas) y ESPERA (derivado de
    activos_analizados - señales_detectadas en salud_agentes, ver docstring
    del módulo). Nunca lanza: ante fallo de red devuelve un resumen con
    error=True, para que generar_reporte() decida qué hacer."""
    try:
        operaciones = _fetch_operaciones(cliente, desde, hasta)
    except RedFailSafeError as e:
        logger.error("No se pudo leer operaciones_ejecutadas para el resumen [%s, %s): %s", desde, hasta, e)
        return {"error": True, "compra": 0, "venta": 0, "espera": 0, "señales": [], "ciclos_analizados": 0}

    try:
        filas_salud = _fetch_salud(cliente, desde, hasta)
    except RedFailSafeError as e:
        logger.warning("No se pudo leer salud_agentes para estimar ESPERA: %s", e)
        filas_salud = []

    compra = [o for o in operaciones if o.get("senal") == "COMPRA"]
    venta = [o for o in operaciones if o.get("senal") == "VENTA"]

    total_analizados = sum((f.get("metricas") or {}).get("activos_analizados", 0) for f in filas_salud)
    total_señales_ciclo = sum((f.get("metricas") or {}).get("señales_detectadas", 0) for f in filas_salud)
    espera_estimado = max(0, total_analizados - total_señales_ciclo)

    señales = [
        {
            "activo": o.get("activo"),
            "tipo": o.get("senal"),
            "precio": o.get("precio_entrada"),
            "motivo": o.get("motivo"),
            "hash_control": o.get("hash_control"),
            "timestamp": o.get("timestamp"),
        }
        for o in (compra + venta)
    ]

    return {
        "error": False,
        "compra": len(compra),
        "venta": len(venta),
        "espera": espera_estimado,
        "señales": señales,
        "ciclos_analizados": len(filas_salud),
    }


def detectar_tendencias(señales: List[Dict[str, Any]]) -> List[str]:
    """Patrones simples sobre las señales COMPRA/VENTA del período: activos
    con 2+ señales del mismo tipo. No es un modelo predictivo -- es un
    conteo legible, a propósito, para que el humano que lee el reporte
    decida si amerita atención."""
    por_activo_tipo: Dict[tuple, int] = defaultdict(int)
    for s in señales:
        por_activo_tipo[(s["activo"], s["tipo"])] += 1

    tendencias = []
    for (activo, tipo), n in sorted(por_activo_tipo.items(), key=lambda kv: -kv[1]):
        if n >= 2:
            tendencias.append(f"{activo} ha tenido {n} señales de {tipo} en el período.")
    return tendencias


@red_segura()
def _insertar_reporte(cliente, fila: Dict[str, Any]) -> None:
    cliente.table(TABLA_REPORTES).insert(fila).execute()


@red_segura()
def _fetch_ultimo_reporte(cliente, tipo: str) -> Optional[Dict[str, Any]]:
    resp = (
        cliente.table(TABLA_REPORTES)
        .select("created_at")
        .eq("tipo", tipo)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def generar_reporte(cliente, tipo: str, ahora: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Genera y persiste un reporte de `tipo` ('horario'/'diario'/'semanal'/
    'quincenal'/'mensual') cubriendo la ventana [ahora - VENTANA, ahora).
    Devuelve la fila insertada, o None si no se pudo generar (ver logs) --
    nunca lanza salvo `tipo` inválido (error de programación del llamador,
    no una falla de runtime)."""
    if tipo not in VENTANAS_REPORTE_HORAS:
        raise ValueError(f"tipo de reporte desconocido: {tipo!r} (válidos: {list(VENTANAS_REPORTE_HORAS)})")

    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(hours=VENTANAS_REPORTE_HORAS[tipo])

    resumen = generar_resumen(cliente, desde, ahora)
    if resumen["error"]:
        logger.error("Reporte '%s' no generado: fallo leyendo operaciones_ejecutadas.", tipo)
        return None

    tendencias = detectar_tendencias(resumen["señales"])

    fila = {
        "tipo": tipo,
        "periodo": ahora.isoformat(),
        "resumen": {
            "compra": resumen["compra"],
            "venta": resumen["venta"],
            "espera": resumen["espera"],
            "ciclos_analizados": resumen["ciclos_analizados"],
        },
        "detalle": {"señales": resumen["señales"]},
        "tendencias": {"patrones": tendencias},
    }

    try:
        _insertar_reporte(cliente, fila)
    except RedFailSafeError as e:
        logger.critical("Fail-safe de red guardando reporte '%s' en %s: %s", tipo, TABLA_REPORTES, e)
        return None

    logger.info("Reporte '%s' generado: %d COMPRA, %d VENTA, ~%d ESPERA, %d tendencia(s).",
                tipo, resumen["compra"], resumen["venta"], resumen["espera"], len(tendencias))

    if resumen["compra"] or resumen["venta"] or tendencias:
        resumen_txt = f"Reporte {tipo}: {resumen['compra']} COMPRA, {resumen['venta']} VENTA."
        if tendencias:
            resumen_txt += " " + " ".join(tendencias)
        enviar_alerta(resumen_txt, nivel="INFO")

    return fila


def generar_reportes_vencidos(cliente, ahora: Optional[datetime] = None) -> List[str]:
    """Recorre los 5 tipos de reporte y genera los que ya vencieron (nunca
    se generó uno, o pasó más tiempo que su ventana desde el último).
    Pensado para llamarse en cada ciclo de trading_orchestrator.py -- no hay
    scheduler separado, el propio Cron de Railway (~cada 5 min) hace de
    "tick". Nunca lanza: un fallo generando un tipo de reporte no debe
    frenar el ciclo de trading ni a los demás tipos."""
    ahora = ahora or datetime.now(timezone.utc)
    generados = []
    for tipo, horas in VENTANAS_REPORTE_HORAS.items():
        try:
            ultimo = _fetch_ultimo_reporte(cliente, tipo)
        except RedFailSafeError as e:
            logger.error("No se pudo consultar el último reporte '%s' (se omite este ciclo): %s", tipo, e)
            continue

        if ultimo and ultimo.get("created_at"):
            try:
                creado = datetime.fromisoformat(str(ultimo["created_at"]).replace("Z", "+00:00"))
                if ahora - creado < timedelta(hours=horas):
                    continue
            except ValueError:
                logger.warning("created_at inválido en el último reporte '%s' (%r), se genera de nuevo.",
                               tipo, ultimo.get("created_at"))

        try:
            if generar_reporte(cliente, tipo, ahora=ahora):
                generados.append(tipo)
        except Exception:
            logger.error("Excepción no controlada generando el reporte '%s':\n%s", tipo, traceback.format_exc())
            continue
    return generados


def main() -> None:
    import argparse
    from core.db_manager import DatabaseManager

    parser = argparse.ArgumentParser(description="Genera un reporte de trading manualmente (fuera del ciclo normal)")
    parser.add_argument("--tipo", choices=list(VENTANAS_REPORTE_HORAS), required=True)
    args = parser.parse_args()

    cliente = DatabaseManager.get_service_client()
    fila = generar_reporte(cliente, args.tipo)
    if fila:
        print(json.dumps(fila, indent=2, ensure_ascii=False, default=str))
    else:
        print("No se pudo generar el reporte (ver logs).")
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
