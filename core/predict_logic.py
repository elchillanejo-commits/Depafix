from core.db_manager import db
import unicodedata
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# UF de referencia de la Tabla de Precios Referenciales DS27 Región Metropolitana
# (05-03-2025), para convertir a CLP las filas con moneda='UF'. Sin esto,
# valor_unitario en UF (rango ~0.01-10) se devuelve crudo y arruina el
# resultado (ver datos/serviu_2026.json -> meta.uf_referencia_documento).
UF_REFERENCIA_SERVIU = 38377.09

def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower().strip()
    return ' '.join(texto.split())

def _valor_en_clp(row):
    valor = float(row['valor_unitario'])
    if row.get('moneda') == 'UF':
        valor *= UF_REFERENCIA_SERVIU
    return valor

def obtener_precio_referencia(nombre_item, prioridad_ok=True):
    """
    Busca precio en precios_serviu, convertido a CLP.
    Si prioridad_ok=True, primero busca en estado_dato='OK', luego en ERROR_DATOS.
    """
    try:
        norm_busqueda = normalizar(nombre_item)
        # 1. Prioridad: estado_dato='OK'
        if prioridad_ok:
            result = db.table('precios_serviu').select('*').eq('estado_dato', 'OK').execute()
            for row in result.data:
                if normalizar(row['item']) == norm_busqueda:
                    return _valor_en_clp(row)
            # Coincidencia parcial en OK
            for row in result.data:
                if norm_busqueda in normalizar(row['item']):
                    logger.info(f"⚠️ Coincidencia parcial en OK: '{nombre_item}' → {row['item']}")
                    return _valor_en_clp(row)
        # 2. Fallback: ERROR_DATOS (con advertencia)
        result = db.table('precios_serviu').select('*').eq('estado_dato', 'ERROR_DATOS').execute()
        for row in result.data:
            if normalizar(row['item']) == norm_busqueda:
                logger.warning(f"⚠️ Precio de ERROR_DATOS usado para '{nombre_item}' → {row['item']}")
                return _valor_en_clp(row)
        for row in result.data:
            if norm_busqueda in normalizar(row['item']):
                logger.warning(f"⚠️ Coincidencia parcial en ERROR_DATOS: '{nombre_item}' → {row['item']}")
                return _valor_en_clp(row)
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
