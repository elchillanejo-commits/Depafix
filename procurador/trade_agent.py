#!/usr/bin/env python3
"""
trade_agent.py -- Detección de anomalías de precio en licitaciones adjudicadas
(precios_serviu: SERVIU + Mercado Público).

Nombre heredado de la conversación con el usuario ("Agente de Trading"), pero
esto no ejecuta órdenes ni opera ningún mercado: es detección estadística de
outliers. Una "anomalía" es un ítem adjudicado cuyo precio se aleja del
promedio de su rubro más de lo esperable (por defecto, 20%) -- una señal para
revisión humana, no una decisión automática de nada.

Arquitectura (infraestructura separada de lógica de negocio):
    - SupabaseClientManager: toda la conexión a Supabase (lectura anon,
      escritura service_role), con reintentos exponenciales (backoff, ver
      core/resiliencia.py) en cada llamada de red. No sabe nada de rubros,
      estadísticas ni anomalías.
    - TradeAgent: la lógica de negocio (estadísticas por rubro, detección de
      anomalías). No conoce clientes de Supabase ni política de reintentos --
      le pide datos a SupabaseClientManager y le entrega lo que hay que
      auditar/reportar.

Flujo:
    1. reglas_rubros define los "rubros críticos" (los que el negocio
       clasifica activamente) -- filtra el ruido de ítems ajenos.
    2. precios_serviu y v_analisis_desviacion (ver
       01_SERVIU/create_view_analisis_desviacion.sql) se leen en paralelo (hilos,
       no asyncio -- ver SupabaseClientManager.cargar_datos): son
       independientes entre sí, ambas solo dependen de los rubros críticos.
       Si la vista no existe o falla, las estadísticas se recalculan en
       Python a partir de las filas ya traídas -- no se detiene el flujo.
    3. Si Supabase falla al leer precios_serviu, se usa el último snapshot
       cacheado en disco (cache_trade_agent.json), dejando explícito en el
       reporte que los datos pueden estar desactualizados.
    4. Cada ítem se procesa en su propio try/except: un dato corrupto no
       aborta el análisis del resto.
    5. Cada alerta se audita en alertas_precio_serviu (Supabase) con un
       hash_control SHA-256. Al final de la corrida se reporta el estado del
       proceso (HEALTHY/CRITICAL) a salud_agentes, para que Siegfried (u otro
       monitor) sepa si el proceso vive sin tener que entrar al servidor.

Salida (exit code), mismo objetivo que salud_agentes pero sin depender de
Supabase -- útil si el propio reporte de salud no llegó a escribirse:
    0 = corrida normal, con datos frescos de Supabase (haya o no anomalías).
    1 = corrida degradada: no hubo datos frescos (Supabase no respondió tras
        los reintentos) y se usó caché local, o no hubo datos en absoluto.
    2 = excepción no controlada: revisar trade_agent.log.

Nota sobre cadencia (ver STATUS.md): precios_serviu cambia cuando corre el
scraping de licitaciones, no continuamente -- correr esto cada minuto sería
carga sin beneficio. Además este agente está marcado "en pausa" por un
problema de normalización de unidades (falsos positivos); revisar STATUS.md
antes de reactivar un cron en serio.

Uso:
    python3 core/trade_agent.py [--umbral 0.20] [--min-muestra 3] [--salida reporte_trading.jsonl]
"""
import argparse
import hashlib
import json
import logging
import statistics
import sys
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Mismo patrón que core/auditor_ia.py y core/auditor_precios_ia.py: no se toca
# sys.path fuera de esto. Se calcula desde __file__ (no se importa
# config.settings.BASE_DIR acá) para evitar el problema del huevo y la
# gallina: este bloque es justamente lo que hace que "config" sea
# importable en primer lugar.
CORE_PATH = Path(__file__).resolve().parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from DepaFix.core.db_manager import DatabaseManager
from DepaFix.core.predict_logic import _valor_en_clp  # misma conversión UF->CLP que usa /predict
from DepaFix.core.resiliencia import red_segura, RedFailSafeError

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
TABLA_ALERTAS = "alertas_precio_serviu"
TABLA_SALUD = "salud_agentes"
NOMBRE_PROCESO = "trade_agent"
# HEALTHY/CRITICAL es el vocabulario semántico que usa este archivo; la
# columna real "estado" en Supabase solo acepta ('online', 'error') -- ver
# el mismo mapeo en procurador/core/salud_agentes.py.
_ESTADO_A_COLUMNA = {"HEALTHY": "online", "CRITICAL": "error"}
UMBRAL_DEFAULT = 0.20
MIN_MUESTRA_DEFAULT = 3
# Última línea de defensa si reglas_rubros también es inalcanzable: los 5
# rubros que el negocio usa hoy (ver Aquiles/scrapers/multi_dia.py::RUBROS).
RUBROS_FALLBACK = ["Construcción", "Electricidad", "Fontanería", "Gráfica", "Capacitación"]


class SupabaseClientManager:
    """Capa de infraestructura: conexiones a Supabase (anon para lectura,
    service_role para escritura/auditoría) con reintentos exponenciales
    (backoff, ver core/resiliencia.py) en cada llamada de red. Aísla a
    TradeAgent de todo lo relacionado con clientes, credenciales y política
    de reintentos -- TradeAgent solo le pide datos y le entrega resultados.

    Las credenciales nunca están hardcodeadas acá: DatabaseManager las lee de
    os.getenv() (SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY), ver
    core/db_manager.py y la sección de variables de entorno en el README.
    """

    def __init__(self) -> None:
        self.lectura = None
        self.escritura = None
        try:
            self.lectura = DatabaseManager.get_client()
        except Exception as e:
            logger.error("No se pudo inicializar el cliente Supabase (anon): %s", e)

        try:
            # service_role: el único que puede escribir en alertas_precio_serviu
            # y salud_agentes (RLS activado sin policy para anon a propósito,
            # ver 01_SERVIU/create_alertas_precio_serviu.sql y 01_SERVIU/create_salud_agentes.sql).
            self.escritura = DatabaseManager.get_service_client()
        except Exception as e:
            logger.error("No se pudo inicializar Supabase (service_role) para auditoría/salud: %s", e)

    # ---------- lectura: rubros críticos ----------

    @red_segura()
    def _fetch_rubros(self) -> List[str]:
        resp = self.lectura.table("reglas_rubros").select("rubro").execute()
        return sorted({r["rubro"] for r in (resp.data or []) if r.get("rubro")})

    def rubros_criticos(self) -> List[str]:
        """Rubros críticos desde reglas_rubros, con reintentos. Si Supabase
        no responde tras agotarlos, cae a RUBROS_FALLBACK."""
        if self.lectura:
            try:
                rubros = self._fetch_rubros()
                if rubros:
                    logger.info("Rubros críticos desde reglas_rubros: %s", rubros)
                    return rubros
            except RedFailSafeError as e:
                logger.error("No se pudo leer reglas_rubros tras reintentos: %s", e)
        logger.warning("Usando lista de rubros críticos de respaldo: %s", RUBROS_FALLBACK)
        return RUBROS_FALLBACK

    # ---------- lectura: precios, con caché de resiliencia en disco ----------

    def _guardar_cache(self, rubros: List[str], filas: List[Dict[str, Any]]) -> None:
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

    def _leer_cache(self, rubros: List[str]) -> Tuple[List[Dict[str, Any]], bool]:
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

    @red_segura()
    def _fetch_precios(self, rubros: List[str]) -> List[Dict[str, Any]]:
        resp = (
            self.lectura.table("precios_serviu")
            .select("id,item,valor_unitario,moneda,rubro,created_at")
            .eq("estado_dato", "OK")
            .in_("rubro", rubros)
            .execute()
        )
        return resp.data or []

    def obtener_precios(self, rubros: List[str]) -> Tuple[List[Dict[str, Any]], bool]:
        """Devuelve (filas, desde_cache)."""
        if self.lectura:
            try:
                filas = self._fetch_precios(rubros)
                self._guardar_cache(rubros, filas)
                return filas, False
            except RedFailSafeError as e:
                logger.error("Falló la lectura de precios_serviu tras reintentos: %s. Cayendo a caché local.", e)
        return self._leer_cache(rubros)

    # ---------- lectura: vista de estadísticas por rubro ----------

    @red_segura()
    def _fetch_vista(self, rubros: List[str]) -> Dict[str, Dict[str, Any]]:
        resp = self.lectura.table("v_analisis_desviacion").select("*").in_("rubro", rubros).execute()
        return {r["rubro"]: r for r in (resp.data or [])}

    def obtener_stats_vista(self, rubros: List[str]) -> Optional[Dict[str, Dict[str, Any]]]:
        if not self.lectura:
            return None
        try:
            stats = self._fetch_vista(rubros)
            if stats:
                logger.info("Estadísticas obtenidas de v_analisis_desviacion (consulta liviana).")
                return stats
        except RedFailSafeError as e:
            logger.warning(
                "No se pudo usar la vista v_analisis_desviacion tras reintentos (¿existe? ¿permisos?): %s. "
                "Se recalculará en Python a partir de las filas ya traídas.", e,
            )
        return None

    def cargar_datos(self, rubros: List[str]) -> Tuple[List[Dict[str, Any]], bool, Optional[Dict[str, Dict[str, Any]]]]:
        """Lanza en paralelo la lectura de precios_serviu y la vista de
        estadísticas: ninguna depende de la otra, ambas solo dependen de
        `rubros` -- esperarlas en serie solo suma latencia sin necesidad.
        Usa hilos (el mismo mecanismo que ya acota la latencia en
        red_segura), no asyncio/httpx: este agente no llama a ningún
        mercado/exchange, solo a Supabase, y reescribir el cliente a una
        variante async implicaría migrar core/db_manager.py -- compartido
        por otros agentes -- para un ahorro de un puñado de milisegundos.

        Si la lectura de precios cae a caché, la vista de estadísticas se
        descarta (stats_vista=None): con datos de caché, TradeAgent siempre
        recalcula en Python para no mezclar estadísticas frescas con filas
        potencialmente desactualizadas."""
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="trade-agent-fanout") as pool:
            futuro_precios = pool.submit(self.obtener_precios, rubros)
            futuro_stats = pool.submit(self.obtener_stats_vista, rubros)
            filas, desde_cache = futuro_precios.result()
            stats_vista = futuro_stats.result()
        return filas, desde_cache, (None if desde_cache else stats_vista)

    # ---------- escritura: auditoría de alertas ----------

    @staticmethod
    def _hash_alerta(fila: Dict[str, Any]) -> str:
        """SHA-256 sobre una representación canónica (JSON con claves
        ordenadas) de la fila de auditoría, para poder verificar después con
        qué datos exactos se disparó la alerta."""
        payload_json = json.dumps(fila, sort_keys=True, default=str)
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    @red_segura()
    def _insertar_alertas(self, filas: List[Dict[str, Any]]) -> None:
        self.escritura.table(TABLA_ALERTAS).insert(filas).execute()

    def registrar_alertas(self, alertas: List[Dict[str, Any]], desde_cache: bool) -> None:
        """Persiste cada alerta en alertas_precio_serviu con su hash_control.
        Una sola llamada de red para todo el lote, no una por alerta -- baja
        latencia y respeta el fail-safe de red_segura como una sola unidad en
        vez de N."""
        if not alertas:
            return
        if not self.escritura:
            logger.error(
                "Cliente Supabase (service_role) no disponible: %d alerta(s) NO quedaron auditadas en %s "
                "(solo quedaron en el reporte local).", len(alertas), TABLA_ALERTAS,
            )
            return

        filas = []
        for alerta in alertas:
            fila = {
                "item_id": alerta.get("id"),
                "item": alerta.get("item"),
                "rubro": alerta.get("rubro"),
                "valor_clp": alerta.get("valor_clp"),
                "promedio_rubro_clp": alerta.get("promedio_rubro_clp"),
                "desviacion_pct": alerta.get("desviacion_pct"),
                "z_score": alerta.get("z_score"),
                "tipo": alerta.get("tipo"),
                "severidad": alerta.get("severidad"),
                "n_muestras_rubro": alerta.get("n_muestras_rubro"),
                "desde_cache": desde_cache,
                "detectado_at": alerta.get("detectado_at"),
            }
            fila["hash_control"] = self._hash_alerta(fila)
            filas.append(fila)

        try:
            self._insertar_alertas(filas)
            logger.info("%d alerta(s) auditada(s) en %s.", len(filas), TABLA_ALERTAS)
        except RedFailSafeError as e:
            logger.critical(
                "Fail-safe de red registrando auditoría en %s: %s. Las alertas quedaron en el reporte "
                "local pero NO en Supabase.", TABLA_ALERTAS, e,
            )

    # ---------- escritura: salud del proceso (observabilidad para Siegfried) ----------

    @red_segura()
    def _insertar_salud(self, fila: Dict[str, Any]) -> None:
        self.escritura.table(TABLA_SALUD).insert(fila).execute()

    def reportar_salud(self, estado: str, detalle: str, metricas: Optional[Dict[str, Any]] = None) -> None:
        """Escribe una fila en salud_agentes con estado 'HEALTHY' o
        'CRITICAL' para que Siegfried (u otro monitor) sepa si el proceso
        corrió bien sin tener que entrar al servidor ni parsear logs.
        Reportar salud nunca debe hacer caer al proceso que está siendo
        monitoreado: cualquier falla acá se loguea, nunca se propaga."""
        fila = {
            # Nombres de columna reales en Supabase (agente/mensaje/
            # ultimo_ciclo, no proceso/detalle/corrido_at -- ver
            # procurador/core/salud_agentes.py, mismo fix).
            "agente": NOMBRE_PROCESO,
            "estado": _ESTADO_A_COLUMNA.get(estado, estado),
            "mensaje": detalle,
            "metricas": metricas or {},
            "ultimo_ciclo": datetime.now(timezone.utc).isoformat(),
        }
        if not self.escritura:
            logger.error("Cliente Supabase (service_role) no disponible: no se pudo reportar salud (%s) a %s.",
                         estado, TABLA_SALUD)
            return
        try:
            self._insertar_salud(fila)
            logger.info("Salud reportada a %s: %s (%s)", TABLA_SALUD, estado, detalle)
        except RedFailSafeError as e:
            logger.error("No se pudo reportar salud a %s tras reintentos: %s", TABLA_SALUD, e)


class TradeAgent:
    """Lógica de negocio: estadísticas por rubro y detección de anomalías de
    precio. No conoce clientes de Supabase ni política de reintentos -- eso
    vive en SupabaseClientManager (self.db)."""

    def __init__(self, umbral: float = UMBRAL_DEFAULT, min_muestra: int = MIN_MUESTRA_DEFAULT,
                 db: Optional[SupabaseClientManager] = None):
        self.umbral = umbral
        self.min_muestra = min_muestra
        self.db = db or SupabaseClientManager()

    # ---------- estadísticas por rubro: fallback en Python ----------

    def _stats_en_python(self, filas: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
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

    def detectar_anomalias(self, filas: List[Dict[str, Any]], stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    def generar_reporte(self, alertas: List[Dict[str, Any]], salida: str) -> None:
        """Escribe el reporte local en JSONL. No es la auditoría institucional
        (esa vive en Supabase vía SupabaseClientManager.registrar_alertas) --
        es un respaldo plano, legible incluso si Supabase está caído."""
        try:
            with open(salida, "a", encoding="utf-8") as f:
                for alerta in alertas:
                    f.write(json.dumps(alerta, ensure_ascii=False) + "\n")
        except Exception:
            logger.critical("No se pudo escribir el reporte en %s:\n%s", salida, traceback.format_exc())

    # ---------- orquestación ----------

    def ejecutar(self, salida: str = REPORTE_DEFAULT) -> Tuple[List[Dict[str, Any]], bool, int]:
        """Devuelve (alertas, desde_cache, n_filas). n_filas en 0 distingue
        "no hubo ningún dato para analizar" (ni Supabase ni caché) de
        "hubo datos pero ninguna anomalía" -- ambas dejan `alertas` vacía,
        pero solo la primera amerita CRITICAL en salud_agentes (ver main())."""
        rubros = self.db.rubros_criticos()
        filas, desde_cache, stats_vista = self.db.cargar_datos(rubros)
        if not filas:
            logger.warning("Sin datos de precios_serviu para analizar (rubros=%s). Nada que reportar.", rubros)
            return [], desde_cache, 0

        stats = stats_vista or self._stats_en_python(filas)

        alertas = self.detectar_anomalias(filas, stats)
        self.generar_reporte(alertas, salida)
        self.db.registrar_alertas(alertas, desde_cache)

        logger.info(
            "Analizados %d ítems en %d rubro(s) crítico(s) con muestra suficiente. "
            "%d anomalías detectadas (umbral=%.0f%%). Reporte: %s%s",
            len(filas), len(stats), len(alertas), self.umbral * 100, salida,
            " [DATOS DE CACHÉ LOCAL -- posiblemente desactualizados]" if desde_cache else "",
        )
        return alertas, desde_cache, len(filas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Detecta anomalías de precio por rubro en precios_serviu")
    parser.add_argument("--umbral", type=float, default=UMBRAL_DEFAULT, help="Desviación mínima vs. el promedio del rubro para alertar (0.20 = 20%%)")
    parser.add_argument("--min-muestra", type=int, default=MIN_MUESTRA_DEFAULT, help="Mínimo de ítems OK en un rubro para confiar en su promedio/stddev")
    parser.add_argument("--salida", default=REPORTE_DEFAULT)
    args = parser.parse_args()

    agente = TradeAgent(umbral=args.umbral, min_muestra=args.min_muestra)
    try:
        alertas, desde_cache, n_filas = agente.ejecutar(salida=args.salida)
    except Exception:
        logger.critical("Excepción no controlada en trade_agent:\n%s", traceback.format_exc())
        agente.db.reportar_salud("CRITICAL", "Excepción no controlada, ver trade_agent.log")
        sys.exit(2)

    if n_filas == 0:
        agente.db.reportar_salud("CRITICAL", "Sin datos de precios_serviu disponibles (ni Supabase ni caché local)",
                                  metricas={"n_filas": 0})
        sys.exit(1)

    detalle = "Datos de caché local (Supabase no respondió)" if desde_cache else "Datos frescos de Supabase"
    agente.db.reportar_salud("HEALTHY", detalle,
                              metricas={"n_filas": n_filas, "alertas": len(alertas), "desde_cache": desde_cache})
    sys.exit(1 if desde_cache else 0)


if __name__ == "__main__":
    main()
