#!/usr/bin/env python3
"""
auditor_ia.py – Versión resiliente con fallback a JSONL.
"""
import csv
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

<<<<<<< Updated upstream
# Asegurar la ruta del proyecto
CORE_PATH = Path("/home/ibar/Proyectos/DepaFix")
=======
# Asegurar la ruta del proyecto (calculada desde __file__, no importa
# config.settings.BASE_DIR: ese import solo funciona una vez que este
# bloque ya puso la raíz del repo en sys.path).
CORE_PATH = Path(__file__).resolve().parent.parent
>>>>>>> Stashed changes
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from core.db_manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("auditor_ia.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.8
OPENAI_PLACEHOLDER = True
FALLBACK_JSONL = "movimientos_pendientes.jsonl"

class AuditorContable:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.supabase = None
        self.reglas = []
        self._init_supabase()

    def _init_supabase(self):
        try:
            self.supabase = DatabaseManager.get_client()
            resp = self.supabase.table("reglas_contables") \
                                .select("*") \
                                .order("prioridad", desc=True) \
                                .execute()
            self.reglas = resp.data
            logger.info("Conectado a Supabase y reglas cargadas (%d).", len(self.reglas))
        except Exception as e:
            logger.error("✍ No se pudo conectar a Supabase: %s\nSe usará modo local.", e)
            self.supabase = None

    def _buscar_en_reglas(self, descripcion):
        if not self.reglas:
            return None, 0, None
        desc_lower = descripcion.lower()
        mejor_conf = 0
        mejor_regla = None
        for regla in self.reglas:
            keywords = json.loads(regla.get("palabras_clave_json", "[]"))
            if not keywords:
                continue
            aciertos = sum(1 for kw in keywords if kw.lower() in desc_lower)
            if aciertos > 0:
                confianza = aciertos / len(keywords)
                if confianza > mejor_conf:
                    mejor_conf = confianza
                    mejor_regla = regla
        if mejor_regla:
            return mejor_regla["cuenta_contable_sugerida"], mejor_conf, mejor_regla["id"]
        return None, 0, None

    def _consultar_openai(self, descripcion, monto):
        if OPENAI_PLACEHOLDER:
            logger.warning("Placeholder OpenAI: %s", descripcion)
            return "CUENTA_NO_DETERMINADA", "Revisar manualmente (OpenAI no configurado)"
        return "CUENTA_NO_DETERMINADA", "Revisar manualmente"

    def _guardar_movimiento(self, monto, descripcion, cuenta, confianza, estado, regla_id, fecha, raw_csv):
        movimiento = {
            "monto": monto,
            "descripcion": descripcion,
            "clasificacion_ia": cuenta,
            "confianza_ia": confianza,
            "estado_revision": estado,
            "regla_usada_id": regla_id,
            "fecha_movimiento": fecha,
            "raw_csv_line": raw_csv,
            "created_at": datetime.utcnow().isoformat()
        }

        if self.supabase:
            try:
                self.supabase.table("auditoria_movimientos").insert(movimiento).execute()
                logger.info("✅ Clasificado: %s → %s (%.2f)", descripcion[:30], cuenta, confianza)
                return
            except Exception as e:
                logger.error("✍ Error al insertar en Supabase: %s\n   → Guardando en fallback local.", e)

        try:
            with open(FALLBACK_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps(movimiento, ensure_ascii=False) + "\n")
            logger.info("📂 Guardado localmente (fallback): %s", descripcion[:30])
        except Exception as e:
            logger.critical("🔥 No se pudo guardar de ninguna forma: %s\n%s", descripcion[:30], traceback.format_exc())

    def procesar_csv(self):
        if not os.path.exists(self.csv_path):
            logger.error("El archivo %s no existe.", self.csv_path)
            return
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            movimientos = list(reader)
        logger.info("Procesando %d movimientos...", len(movimientos))
        for row in movimientos:
            descripcion = row.get("descripcion", "").strip()
            monto = float(row.get("monto", 0))
            fecha = row.get("fecha", datetime.utcnow().strftime("%Y-%m-%d"))
            cuenta, confianza, regla_id = self._buscar_en_reglas(descripcion)
            if cuenta is None or confianza < CONFIDENCE_THRESHOLD:
                cuenta_sugerida, _ = self._consultar_openai(descripcion, monto)
                if cuenta is None:
                    cuenta = cuenta_sugerida
                    confianza = 0.0
                else:
                    cuenta = cuenta_sugerida
                    confianza = 0.5
            estado = "CLASIFICADO" if (confianza >= CONFIDENCE_THRESHOLD and cuenta != "CUENTA_NO_DETERMINADA") else "PENDIENTE_REVISION"
            self._guardar_movimiento(monto, descripcion, cuenta, confianza, estado, regla_id, fecha, json.dumps(row, ensure_ascii=False))
        logger.info("Procesamiento finalizado. Revisa %s si hubo fallos.", FALLBACK_JSONL)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python auditor_ia.py movimientos.csv")
        sys.exit(1)
    auditor = AuditorContable(sys.argv[1])
    auditor.procesar_csv()