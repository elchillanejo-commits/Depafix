#!/usr/bin/env python3
"""
bi_exporter.py -- exporta la tabla de presupuestos a un CSV limpio (tipos
correctos, sin nulos en columnas requeridas) para que Power BI lo consuma
por "Get Data > Text/CSV" o por refresh programado sobre esa ruta.

ADVERTENCIA (auditoría 2026-07-16, verificado en vivo contra Supabase): la
tabla "presupuestos_generados" NO existe -- PostgREST responde PGRST205
("Could not find the table 'public.presupuestos_generados'") y sugiere
"public.presupuestos". El rol/schema "bi_readonly" tampoco existe en este
repo (no aparece en supabase_schema.sql ni create_tokens_tables.sql). Este
exporter apunta por default a "presupuestos" -- la tabla real, confirmada
con datos en vivo -- con columnas: id, cliente, tarea, maestro, fecha, total,
m2, estado, descripcion, incluye_materiales, created_at. Usa --tabla si
"presupuestos_generados" termina siendo una tabla nueva/futura distinta.

Nunca inventa valores para nulos: una fila que falla la validación se
descarta del CSV limpio y queda registrada (con el motivo) en el CSV de
rechazados, para revisión humana -- igual que el resto del proyecto no
fabrica datos financieros que no existen.

Uso:
    python3 src/analytics/bi_exporter.py [--tabla presupuestos_generados] [--out data/bi_export/presupuestos_bi.csv]
"""
import argparse
import csv
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

CORE_PATH = Path(__file__).resolve().parent.parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from config.settings import BASE_DIR
from core.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TABLA_DEFAULT = "presupuestos"
TAMANO_PAGINA = 1000

# Columnas reales de "presupuestos" (confirmadas 2026-07-16 leyendo filas en
# vivo). tipo: "numerico" | "texto" | "fecha" | "booleano". requerido=True ->
# la fila se rechaza del CSV limpio si esa columna falta o es null.
ESQUEMA_ESPERADO = {
    "id":                  {"tipo": "numerico", "requerido": True},
    "cliente":             {"tipo": "texto",     "requerido": True},
    "tarea":               {"tipo": "texto",     "requerido": False},
    "maestro":             {"tipo": "texto",     "requerido": False},
    "fecha":               {"tipo": "fecha",     "requerido": True},
    "total":               {"tipo": "numerico",  "requerido": True},
    "m2":                  {"tipo": "numerico",  "requerido": False},
    "estado":              {"tipo": "texto",     "requerido": True},
    "descripcion":         {"tipo": "texto",     "requerido": False},
    "incluye_materiales":  {"tipo": "booleano",  "requerido": False},
}


def _validar_numerico(valor):
    if isinstance(valor, bool):
        raise ValueError("booleano, no numérico")
    return float(valor)


def _validar_fecha(valor):
    texto = str(valor).strip()
    # Supabase/Postgres devuelve ISO 8601; acepta con o sin 'Z'.
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).isoformat()


def _validar_texto(valor):
    texto = str(valor).strip()
    if not texto:
        raise ValueError("texto vacío")
    return texto


def _validar_booleano(valor):
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        v = valor.strip().lower()
        if v in ("true", "t", "1"):
            return True
        if v in ("false", "f", "0"):
            return False
    raise ValueError(f"'{valor}' no es un booleano reconocible")


VALIDADORES = {
    "numerico": _validar_numerico,
    "fecha": _validar_fecha,
    "texto": _validar_texto,
    "booleano": _validar_booleano,
}


def validar_y_limpiar_fila(fila, esquema=ESQUEMA_ESPERADO):
    """Devuelve (fila_limpia, None) si pasa, o (None, motivo) si se rechaza.
    Cada columna del esquema se valida por separado -- una columna opcional
    mala no rechaza la fila entera, solo se deja tal cual viene."""
    limpia = dict(fila)
    for columna, regla in esquema.items():
        valor = fila.get(columna)
        faltante = valor is None or (isinstance(valor, str) and not valor.strip())

        if faltante:
            if regla["requerido"]:
                return None, f"columna requerida '{columna}' está vacía/null"
            continue

        try:
            limpia[columna] = VALIDADORES[regla["tipo"]](valor)
        except (ValueError, TypeError) as e:
            if regla["requerido"]:
                return None, f"columna '{columna}' no cumple tipo '{regla['tipo']}': {e}"
            limpia[columna] = None

    return limpia, None


def obtener_filas(db, tabla):
    """Trae todas las filas paginando de a TAMANO_PAGINA (evita el límite
    implícito de 1000 filas por request de PostgREST/Supabase)."""
    filas = []
    inicio = 0
    while True:
        try:
            resp = db.table(tabla).select("*").range(inicio, inicio + TAMANO_PAGINA - 1).execute()
        except Exception as e:
            logger.error("Fallo leyendo '%s' (offset %d): %s", tabla, inicio, e)
            break

        lote = resp.data or []
        filas.extend(lote)
        if len(lote) < TAMANO_PAGINA:
            break
        inicio += TAMANO_PAGINA

    return filas


def exportar(tabla=TABLA_DEFAULT, ruta_salida=None, ruta_rechazados=None):
    ruta_salida = Path(ruta_salida) if ruta_salida else BASE_DIR / "data" / "bi_export" / "presupuestos_bi.csv"
    ruta_rechazados = Path(ruta_rechazados) if ruta_rechazados else ruta_salida.with_name(ruta_salida.stem + "_rechazados.csv")
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    try:
        db = DatabaseManager.get_client()
    except Exception as e:
        logger.error("No se pudo inicializar el cliente de Supabase: %s", e)
        return 0, 0

    filas = obtener_filas(db, tabla)
    if not filas:
        logger.warning("La tabla '%s' no devolvió filas (¿no existe, está vacía, o RLS la bloquea?).", tabla)
        return 0, 0

    limpias, rechazadas = [], []
    for fila in filas:
        try:
            fila_limpia, motivo = validar_y_limpiar_fila(fila)
        except Exception:
            fila_limpia, motivo = None, f"excepción inesperada validando fila: {traceback.format_exc()}"

        if fila_limpia is not None:
            limpias.append(fila_limpia)
        else:
            fila_rechazada = dict(fila)
            fila_rechazada["_motivo_rechazo"] = motivo
            rechazadas.append(fila_rechazada)

    if limpias:
        columnas = list(limpias[0].keys())
        with open(ruta_salida, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            writer.writeheader()
            writer.writerows(limpias)
        logger.info("%d filas limpias exportadas a %s", len(limpias), ruta_salida)

    if rechazadas:
        columnas_rechazo = list(rechazadas[0].keys())
        with open(ruta_rechazados, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas_rechazo)
            writer.writeheader()
            writer.writerows(rechazadas)
        logger.warning("%d filas rechazadas (revisar %s)", len(rechazadas), ruta_rechazados)

    return len(limpias), len(rechazadas)


def main():
    parser = argparse.ArgumentParser(description="Exporta presupuestos a CSV limpio para Power BI")
    parser.add_argument("--tabla", default=TABLA_DEFAULT)
    parser.add_argument("--out", default=None, help="Ruta del CSV limpio (default: data/bi_export/presupuestos_bi.csv)")
    args = parser.parse_args()

    limpias, rechazadas = exportar(tabla=args.tabla, ruta_salida=args.out)

    if limpias == 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
