from core.db_manager import db
import unicodedata

# UF de referencia de la Tabla de Precios Referenciales DS27 Región Metropolitana
# (05-03-2025), para convertir a CLP las filas con moneda='UF'. Ver
# datos/serviu_2026.json -> meta.uf_referencia_documento.
UF_REFERENCIA_SERVIU = 38377.09

def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower().strip()
    return ' '.join(texto.split())

def _valor_en_clp(row):
    valor = float(row['valor_unitario'])
    if row.get('moneda') == 'UF':
        valor *= UF_REFERENCIA_SERVIU
    return valor

def obtener_precio_referencia(nombre_item):
    """Busca nombre_item en precios_serviu, normalizando acentos/mayúsculas.
    Si hay varias coincidencias (exactas o parciales), usa la más reciente
    (created_at desc) sin importar la fuente, y convierte UF->CLP si aplica."""
    try:
        norm_busqueda = normalizar(nombre_item)
        result = (
            db.table('precios_serviu')
            .select('item,valor_unitario,moneda,created_at')
            .order('created_at', desc=True)
            .execute()
        )
        for row in result.data:
            if normalizar(row['item']) == norm_busqueda:
                return _valor_en_clp(row)
        for row in result.data:
            if norm_busqueda in normalizar(row['item']):
                return _valor_en_clp(row)
    except Exception as e:
        print(f"⚠️ Error: {e}")
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
