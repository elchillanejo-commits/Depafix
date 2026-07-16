#!/usr/bin/env python3
"""
auditor_precios_ia.py – Hito 2.5.

Sanea precios_serviu: busca filas con rubro o valor_unitario en NULL,
intenta clasificar el rubro contra reglas_rubros (palabra clave -> rubro,
por prioridad) y si no puede, marca estado_dato='ERROR_DATOS' para revisión
manual en vez de dejar el dato a medias en silencio.

No reutiliza reglas_contables/core/auditor_ia.py: esa tabla y ese script ya
están en producción clasificando movimientos bancarios en cuentas contables,
un dominio distinto al de clasificar el rubro de un ítem de licitación.

Uso:
    python3 core/auditor_precios_ia.py [--dry-run] [--page-size 200]
"""
import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Mismo patrón que core/auditor_ia.py: no se toca sys.path fuera de esto.
CORE_PATH = Path("/home/ibar/Proyectos/DepaFix")
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.db_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(CORE_PATH / "auditor_precios_ia.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

FALLBACK_JSONL = str(CORE_PATH / "precios_pendientes.jsonl")
PAGE_SIZE_DEFAULT = 200


class AuditorPrecios:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.supabase = None
        self.reglas = []
        self._init_supabase()

    def _init_supabase(self):
        try:
            self.supabase = DatabaseManager.get_client()
            resp = (
                self.supabase.table("reglas_rubros")
                .select("*")
                .order("prioridad", desc=True)
                .execute()
            )
            self.reglas = resp.data
            logger.info("Conectado a Supabase y reglas_rubros cargadas (%d).", len(self.reglas))
        except Exception as e:
            logger.error("No se pudo conectar a Supabase: %s", e)
            self.supabase = None
            self.reglas = []

        self.exclusiones = {}
        if self.supabase:
            try:
                resp = self.supabase.table("reglas_rubros_exclusiones").select("*").execute()
                for fila in resp.data:
                    rubro = fila.get("rubro")
                    palabra = (fila.get("palabra_excluida") or "").lower()
                    if rubro and palabra:
                        self.exclusiones.setdefault(rubro, set()).add(palabra)
                logger.info(
                    "reglas_rubros_exclusiones cargadas (%d rubro(s) con exclusiones).",
                    len(self.exclusiones),
                )
            except Exception as e:
                # Tabla nueva/opcional: si falla, se sigue clasificando sin
                # exclusiones en vez de detener el auditor.
                logger.warning("No se pudieron cargar exclusiones (se seguirá sin ellas): %s", e)

    def _clasificar_rubro(self, item_texto):
        """Devuelve (rubro, regla_id) según la primera regla (ya ordenada por
        prioridad desc) cuya palabra_clave aparezca en item_texto Y cuyo rubro
        no tenga una palabra excluida presente en el mismo texto (ver
        reglas_rubros_exclusiones -- ej. "construcción de barcos" no debe
        clasificar como Construcción). Si una regla calza pero está excluida,
        se sigue probando con las siguientes reglas antes de rendirse."""
        if not item_texto or not self.reglas:
            return None, None
        texto_lower = item_texto.lower()
        for regla in self.reglas:
            palabra = (regla.get("palabra_clave") or "").lower()
            rubro = regla.get("rubro")
            if not palabra or palabra not in texto_lower:
                continue
            excluidas = self.exclusiones.get(rubro, ())
            if any(excl in texto_lower for excl in excluidas):
                continue
            return rubro, regla.get("id")
        return None, None

    def _guardar_fallback(self, row, motivo):
        registro = {
            "id": row.get("id"),
            "item": row.get("item"),
            "motivo": motivo,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(FALLBACK_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            logger.info("Guardado en fallback local (id=%s): %s", row.get("id"), motivo)
        except Exception:
            logger.critical(
                "No se pudo guardar en ninguna parte (id=%s):\n%s",
                row.get("id"),
                traceback.format_exc(),
            )

    def _actualizar_fila(self, row_id, cambios):
        if self.dry_run:
            logger.info("[dry-run] update id=%s -> %s", row_id, cambios)
            return True
        try:
            self.supabase.table("precios_serviu").update(cambios).eq("id", row_id).execute()
            return True
        except Exception as e:
            logger.error("Error al actualizar precios_serviu id=%s: %s", row_id, e)
            return False

    def _procesar_fila(self, row):
        """Bulletproof por diseño: cualquier excepción se loguea y la fila se
        deja en estado_dato=ERROR_DATOS (best-effort) sin detener el resto del
        lote."""
        row_id = row.get("id")
        try:
            item = row.get("item")
            valor_unitario = row.get("valor_unitario")
            rubro_actual = row.get("rubro")

            if valor_unitario is None:
                logger.warning(
                    "id=%s '%s': valor_unitario ausente, no se puede inferir el precio. Marcando ERROR_DATOS.",
                    row_id, item,
                )
                if not self._actualizar_fila(row_id, {"estado_dato": "ERROR_DATOS"}):
                    self._guardar_fallback(row, "valor_unitario NULL, update falló")
                return

            if rubro_actual is None:
                rubro, regla_id = self._clasificar_rubro(item)
                if rubro:
                    ok = self._actualizar_fila(row_id, {"rubro": rubro, "estado_dato": "OK"})
                    if ok:
                        logger.info("id=%s '%s' -> rubro=%s (regla=%s)", row_id, item, rubro, regla_id)
                    else:
                        self._guardar_fallback(row, f"clasificado como {rubro} pero update falló")
                else:
                    logger.warning(
                        "id=%s '%s': ninguna regla de reglas_rubros calzó. Marcando ERROR_DATOS.",
                        row_id, item,
                    )
                    if not self._actualizar_fila(row_id, {"estado_dato": "ERROR_DATOS"}):
                        self._guardar_fallback(row, "sin regla de rubro, update falló")
        except Exception:
            logger.error(
                "Excepción no controlada procesando id=%s:\n%s", row_id, traceback.format_exc()
            )
            self._guardar_fallback(row, "excepción no controlada, ver auditor_precios_ia.log")

    def procesar(self, page_size=PAGE_SIZE_DEFAULT):
        if not self.supabase:
            logger.error("Sin conexión a Supabase, no se puede procesar. Revisa .env.")
            return

        total = 0
        procesados_ids = set()
        while True:
            try:
                # Siempre se lee desde el principio del filtro: las filas ya
                # saneadas dejan de calzar is.null y desaparecen del resultado,
                # así que la "próxima página" es siempre lo que sigue pendiente.
                resp = (
                    self.supabase.table("precios_serviu")
                    .select("id,item,valor_unitario,rubro,estado_dato")
                    .or_("rubro.is.null,valor_unitario.is.null")
                    .range(0, page_size - 1)
                    .execute()
                )
            except Exception as e:
                logger.error("Error al leer página de precios_serviu: %s", e)
                break

            filas = resp.data or []
            if not filas:
                break

            filas_nuevas = [f for f in filas if f.get("id") not in procesados_ids]
            if not filas_nuevas:
                # dry-run, o las escrituras están fallando: las mismas filas
                # siguen sin resolverse. Cortar acá evita un loop infinito.
                logger.warning(
                    "Sin progreso: las %d filas devueltas ya se procesaron en esta corrida "
                    "y siguen sin resolverse (¿--dry-run o fallos de escritura?). Deteniendo.",
                    len(filas),
                )
                break

            for row in filas_nuevas:
                self._procesar_fila(row)
                procesados_ids.add(row.get("id"))
                total += 1

            if len(filas) < page_size:
                break

        logger.info("Procesamiento finalizado. %d filas revisadas. Revisa %s si hubo fallos.", total, FALLBACK_JSONL)


def main():
    parser = argparse.ArgumentParser(description="Audita y sanea rubro/valor_unitario en precios_serviu")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en Supabase, solo loguea lo que haría")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE_DEFAULT)
    args = parser.parse_args()

    auditor = AuditorPrecios(dry_run=args.dry_run)
    auditor.procesar(page_size=args.page_size)


if __name__ == "__main__":
    main()
