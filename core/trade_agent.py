#!/usr/bin/env python3
"""
trade_agent.py -- Detección de anomalías de precio en licitaciones adjudicadas
(precios_serviu: SERVIU + Mercado Público).

Nombre heredado de la conversación con el usuario ("Agente de Trading"), pero
esto no ejecuta órdenes ni opera ningún mercado: es detección estadística de
outliers. Una "anomalía" es un ítem adjudicado cuyo precio se aleja del
promedio de su rubro más de lo esperable (por defecto, 20%) -- una señal para
revisión humana, no una decisión automática de nada.

Flujo:
    1. reglas_rubros define los "rubros críticos" (los que el negocio
       clasifica activamente) -- filtra el ruido de ítems ajenos.
    2. v_analisis_desviacion (ver sql/create_view_analisis_desviacion.sql) da
       promedio/stddev por rubro en una sola consulta liviana. Si no existe o
       falla, se recalculan las mismas estadísticas en Python a partir de las
       filas ya traídas -- no se detiene el flujo.
    3. Si Supabase falla al leer precios_serviu, se usa el último snapshot
       cacheado en disco (cache_trade_agent.json), dejando explícito en el
       reporte que los datos pueden estar desactualizados.
    4. Cada ítem se procesa en su propio try/except: un dato corrupto no
       aborta el análisis del resto.

Uso:
    python3 core/trade_agent.py [--umbral 0.20] [--min-muestra 3] [--salida reporte_trading.jsonl]
"""
import argparse
import json
import logging
import statistics
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Mismo patrón que core/auditor_ia.py y core/auditor_precios_ia.py: no se toca
# sys.path fuera de esto.
CORE_PATH = Path("/home/ibar/Proyectos/DepaFix")
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.db_manager import DatabaseManager
from core.predict_logic import _valor_en_clp  # misma conversión UF->CLP que usa /predict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(CORE_PATH / "trade_agent.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CACHE_PATH = CORE_PATH / "cache_trade_agent.json"
REPORTE_DEFAULT = str(CORE_PATH / "reporte_trading.jsonl")
UMBRAL_DEFAULT = 0.20
MIN_MUESTRA_DEFAULT = 3
# Última línea de defensa si reglas_rubros también es inalcanzable: los 5
# rubros que el negocio usa hoy (ver Aquiles/scrapers/multi_dia.py::RUBROS).
RUBROS_FALLBACK = ["Construcción", "Electricidad", "Fontanería", "Gráfica", "Capacitación"]


class TradeAgent:
    def __init__(self, umbral=UMBRAL_DEFAULT, min_muestra=MIN_MUESTRA_DEFAULT):
        self.umbral = umbral
        self.min_muestra = min_muestra
        self.supabase = None
        try:
            self.supabase = DatabaseManager.get_client()
        except Exception as e:
            logger.error("No se pudo inicializar el cliente de Supabase: %s", e)

    # ---------- rubros críticos (integración con reglas_rubros) ----------

    def _rubros_criticos(self):
        if self.supabase:
            try:
                resp = self.supabase.table("reglas_rubros").select("rubro").execute()
                rubros = sorted({r["rubro"] for r in (resp.data or []) if r.get("rubro")})
                if rubros:
                    logger.info("Rubros críticos desde reglas_rubros: %s", rubros)
                    return rubros
            except Exception as e:
                logger.error("No se pudo leer reglas_rubros: %s", e)
        logger.warning("Usando lista de rubros críticos de respaldo: %s", RUBROS_FALLBACK)
        return RUBROS_FALLBACK

    # ---------- lectura de precios, con caché de resiliencia ----------

    def _guardar_cache(self, rubros, filas):
        try:
            payload = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "rubros_criticos": rubros,
                "filas": filas,
            }
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
        except Exception:
            # No poder cachear no es motivo para abortar el análisis en curso.
            logger.warning("No se pudo escribir el caché local (%s):\n%s", CACHE_PATH, traceback.format_exc())

    def _leer_cache(self, rubros):
        if not CACHE_PATH.exists():
            logger.critical("Supabase no responde y no hay caché local (%s). Sin datos para analizar.", CACHE_PATH)
            return [], True
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                payload = json.load(f)
            filas = [f for f in payload.get("filas", []) if f.get("rubro") in rubros]
            logger.warning(
                "Usando caché local de la última sesión sincronizada (%s, %d filas relevantes) "
                "porque Supabase no respondió. Los datos pueden estar desactualizados.",
                payload.get("cached_at", "fecha desconocida"), len(filas),
            )
            return filas, True
        except Exception:
            logger.critical("Caché local corrupto o ilegible (%s):\n%s", CACHE_PATH, traceback.format_exc())
            return [], True

    def _fetch_precios(self, rubros):
        """Devuelve (filas, desde_cache)."""
        if self.supabase:
            try:
                resp = (
                    self.supabase.table("precios_serviu")
                    .select("id,item,valor_unitario,moneda,rubro,created_at")
                    .eq("estado_dato", "OK")
                    .in_("rubro", rubros)
                    .execute()
                )
                filas = resp.data or []
                self._guardar_cache(rubros, filas)
                return filas, False
            except Exception as e:
                logger.error("Falló la lectura de precios_serviu desde Supabase: %s. Cayendo a caché local.", e)
        return self._leer_cache(rubros)

    # ---------- estadísticas por rubro: vista liviana, con fallback en Python ----------

    def _stats_via_vista(self, rubros):
        if not self.supabase:
            return None
        try:
            resp = self.supabase.table("v_analisis_desviacion").select("*").in_("rubro", rubros).execute()
            stats = {r["rubro"]: r for r in (resp.data or [])}
            if stats:
                logger.info("Estadísticas obtenidas de v_analisis_desviacion (consulta liviana).")
                return stats
        except Exception as e:
            logger.warning(
                "No se pudo usar la vista v_analisis_desviacion (¿existe? ¿permisos?): %s. "
                "Se recalculará en Python a partir de las filas ya traídas.", e,
            )
        return None

    def _stats_en_python(self, filas):
        por_rubro = defaultdict(list)
        for fila in filas:
            try:
                por_rubro[fila["rubro"]].append(_valor_en_clp(fila))
            except Exception as e:
                logger.warning("No se pudo convertir a CLP la fila id=%s: %s", fila.get("id"), e)
                continue

        stats = {}
        for rubro, valores in por_rubro.items():
            if len(valores) < self.min_muestra:
                continue
            stats[rubro] = {
                "promedio_clp": statistics.mean(valores),
                "stddev_clp": statistics.stdev(valores) if len(valores) > 1 else 0.0,
                "n_muestras": len(valores),
            }
        logger.info("Estadísticas calculadas en Python para %d rubro(s).", len(stats))
        return stats

    # ---------- detección de anomalías ----------

    def detectar_anomalias(self, filas, stats):
        """Recorre cada ítem en su propio try/except: un ítem corrupto se
        loguea y se salta, nunca detiene el análisis del resto."""
        alertas = []
        for fila in filas:
            try:
                rubro = fila.get("rubro")
                stat = stats.get(rubro)
                if not stat:
                    continue
                n_muestras = int(stat.get("n_muestras") or 0)
                promedio = float(stat.get("promedio_clp") or 0)
                if n_muestras < self.min_muestra or promedio <= 0:
                    continue

                valor_clp = _valor_en_clp(fila)
                desviacion_pct = (valor_clp - promedio) / promedio
                if abs(desviacion_pct) < self.umbral:
                    continue

                stddev = float(stat.get("stddev_clp") or 0)
                z_score = (valor_clp - promedio) / stddev if stddev > 0 else None
                if z_score is not None:
                    # Con stddev disponible, el z-score manda: es la medida
                    # correcta de "qué tan atípico" es el valor. Un
                    # desviacion_pct grande con z bajo solo significa que el
                    # rubro tiene mucha varianza (ver Construcción: un ítem de
                    # 6.700M sesga el promedio y hace ver "atípico" a todo lo
                    # demás en términos de %, aunque estén dentro de 1 stddev).
                    severidad = "ALTA" if abs(z_score) >= 2 else "MEDIA"
                else:
                    # stddev=0 (todas las muestras del rubro valen lo mismo):
                    # no hay z-score posible, así que el % contra el promedio
                    # es la única señal disponible.
                    severidad = "ALTA" if abs(desviacion_pct) >= 0.5 else "MEDIA"

                alertas.append({
                    "id": fila.get("id"),
                    "item": fila.get("item"),
                    "rubro": rubro,
                    "valor_clp": round(valor_clp, 2),
                    "promedio_rubro_clp": round(promedio, 2),
                    "desviacion_pct": round(desviacion_pct * 100, 2),
                    "z_score": round(z_score, 2) if z_score is not None else None,
                    "tipo": "SOBREPRECIO" if desviacion_pct > 0 else "SUBPRECIO",
                    "severidad": severidad,
                    "n_muestras_rubro": n_muestras,
                    "detectado_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                logger.error(
                    "Excepción no controlada analizando id=%s ('%s'):\n%s",
                    fila.get("id"), fila.get("item"), traceback.format_exc(),
                )
                continue  # el ítem se descarta, el agente sigue con el resto

        return alertas

    def generar_reporte(self, alertas, salida):
        try:
            with open(salida, "a", encoding="utf-8") as f:
                for alerta in alertas:
                    f.write(json.dumps(alerta, ensure_ascii=False) + "\n")
        except Exception:
            logger.critical("No se pudo escribir el reporte en %s:\n%s", salida, traceback.format_exc())

    # ---------- orquestación ----------

    def ejecutar(self, salida=REPORTE_DEFAULT):
        rubros = self._rubros_criticos()
        filas, desde_cache = self._fetch_precios(rubros)
        if not filas:
            logger.warning("Sin datos de precios_serviu para analizar (rubros=%s). Nada que reportar.", rubros)
            return []

        stats = None if desde_cache else self._stats_via_vista(rubros)
        if not stats:
            stats = self._stats_en_python(filas)

        alertas = self.detectar_anomalias(filas, stats)
        self.generar_reporte(alertas, salida)

        logger.info(
            "Analizados %d ítems en %d rubro(s) crítico(s) con muestra suficiente. "
            "%d anomalías detectadas (umbral=%.0f%%). Reporte: %s%s",
            len(filas), len(stats), len(alertas), self.umbral * 100, salida,
            " [DATOS DE CACHÉ LOCAL -- posiblemente desactualizados]" if desde_cache else "",
        )
        return alertas


def main():
    parser = argparse.ArgumentParser(description="Detecta anomalías de precio por rubro en precios_serviu")
    parser.add_argument("--umbral", type=float, default=UMBRAL_DEFAULT, help="Desviación mínima vs. el promedio del rubro para alertar (0.20 = 20%%)")
    parser.add_argument("--min-muestra", type=int, default=MIN_MUESTRA_DEFAULT, help="Mínimo de ítems OK en un rubro para confiar en su promedio/stddev")
    parser.add_argument("--salida", default=REPORTE_DEFAULT)
    args = parser.parse_args()

    agente = TradeAgent(umbral=args.umbral, min_muestra=args.min_muestra)
    agente.ejecutar(salida=args.salida)


if __name__ == "__main__":
    main()
