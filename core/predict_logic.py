from core.db_manager import db
import unicodedata
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower().strip()
    return ' '.join(texto.split())

def obtener_precio_referencia(nombre_item, prioridad_ok=True):
    """
    Busca precio en precios_serviu.
    Si prioridad_ok=True, primero busca en estado_dato='OK', luego en ERROR_DATOS.
    """
    try:
        norm_busqueda = normalizar(nombre_item)
        # 1. Prioridad: estado_dato='OK'
        if prioridad_ok:
            result = db.table('precios_serviu').select('*').eq('estado_dato', 'OK').execute()
            for row in result.data:
                if normalizar(row['item']) == norm_busqueda:
                    return float(row['valor_unitario'])
            # Coincidencia parcial en OK
            for row in result.data:
                if norm_busqueda in normalizar(row['item']):
                    logger.info(f"⚠️ Coincidencia parcial en OK: '{nombre_item}' → {row['item']}")
                    return float(row['valor_unitario'])
        # 2. Fallback: ERROR_DATOS (con advertencia)
        result = db.table('precios_serviu').select('*').eq('estado_dato', 'ERROR_DATOS').execute()
        for row in result.data:
            if normalizar(row['item']) == norm_busqueda:
                logger.warning(f"⚠️ Precio de ERROR_DATOS usado para '{nombre_item}' → {row['item']}")
                return float(row['valor_unitario'])
        for row in result.data:
            if norm_busqueda in normalizar(row['item']):
                logger.warning(f"⚠️ Coincidencia parcial en ERROR_DATOS: '{nombre_item}' → {row['item']}")
                return float(row['valor_unitario'])
    except Exception as e:
        logger.error(f"Error en obtener_precio_referencia: {e}")
    return None

def predecir_costo(items):
    total = 0
    for item in items:
        desc = item.get('descripcion', '')
        cant = item.get('cantidad', 1)
        precio = obtener_precio_referencia(desc)
        if precio:
            total += precio * cant
        else:
            total += item.get('valor', 0) * cant * 1.2
    return total
