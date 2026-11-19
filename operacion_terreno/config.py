from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XLSX = Path("/home/ibar/Descargas/propiedades_11_2026.xlsx")
DEFAULT_PLAN = PROJECT_ROOT / "PLAN_RUTA_Y_PRESUPUESTOS_STGO.md"
DEFAULT_OUTDIR = PROJECT_ROOT
DATOS_DIR = PROJECT_ROOT / "datos"
SQL_DIR = PROJECT_ROOT / "sql"
DEFAULT_DB_PATH = DATOS_DIR / "terreno_stgo_centro.db"
DEFAULT_CATASTRO = DATOS_DIR / "catastro_referencial_stgo_centro.csv"
DEFAULT_GEOCODE_CACHE = DATOS_DIR / "geocoding_stgo_centro.json"
DEFAULT_NORMALIZED_CSV = DATOS_DIR / "terreno_stgo_centro_normalizado.csv"
DEFAULT_ROUTES_JSON = DATOS_DIR / "rutas_google_maps.json"
DEFAULT_DDL = SQL_DIR / "schema_terreno_stgo_centro.sql"

COMUNA_OBJETIVO = "Santiago"
HOJA_PROPIEDADES = "Propiedades"

ESTADOS = {
    "al dia": "Al día",
    "al día": "Al día",
    "vacante": "Vacante",
    "suspendida": "Suspendida",
    "pago expirado": "Pago expirado",
}
ESTADO_ORDEN = {"Vacante": 0, "Pago expirado": 1, "Suspendida": 2, "Al día": 3}

STREET_DISPLAY = {
    "MORANDE": "Morandé",
    "CATEDRAL": "Catedral",
    "SANTO DOMINGO": "Santo Domingo",
    "LORD COCHRANE": "Lord Cochrane",
    "SAZIE": "Sazié",
    "SAN IGNACIO": "San Ignacio",
    "TARAPACA": "Tarapacá",
    "ALDUNATE": "Aldunate",
    "SAN DIEGO": "San Diego",
    "FRANKLIN": "Franklin",
    "NATANIEL COX": "Nataniel Cox",
    "SAN FRANCISCO": "San Francisco",
    "SAN ISIDRO": "San Isidro",
    "SANTA ISABEL": "Santa Isabel",
    "SANTA VICTORIA": "Santa Victoria",
    "SANTA ROSA": "Santa Rosa",
    "CARMEN": "Carmen",
    "VICUNA MACKENNA": "Vicuña Mackenna",
    "DIAGONAL VICUNA MACKENNA": "Diagonal Vicuña Mackenna",
    "BLANCO ENCALADA": "Blanco Encalada",
    "EJERCITO": "Avenida Ejército",
    "EJERCITO LIBERTADOR": "Avenida Ejército Libertador",
    "TOESCA": "Toesca",
    "ESPANA": "Avenida España",
}

BLOCK_BY_STREET = {
    "BLANCO ENCALADA": "Bloque 1",
    "EJERCITO": "Bloque 1",
    "TOESCA": "Bloque 1",
    "ESPANA": "Bloque 1",
    "MORANDE": "Bloque 2",
    "CATEDRAL": "Bloque 2",
    "SANTO DOMINGO": "Bloque 2",
    "LORD COCHRANE": "Bloque 2",
    "SAZIE": "Bloque 2",
    "SAN IGNACIO": "Bloque 2",
    "TARAPACA": "Bloque 2",
    "ALDUNATE": "Bloque 2",
    "SAN DIEGO": "Bloque 2",
    "FRANKLIN": "Bloque 2",
    "NATANIEL COX": "Bloque 2",
    "SAN FRANCISCO": "Bloque 3",
    "SAN ISIDRO": "Bloque 3",
    "SANTA ISABEL": "Bloque 3",
    "SANTA VICTORIA": "Bloque 3",
    "SANTA ROSA": "Bloque 3",
    "CARMEN": "Bloque 3",
    "VICUNA MACKENNA": "Bloque 3",
    "DIAGONAL VICUNA MACKENNA": "Bloque 3",
}

PLAN_ORDER = {
    ("BLANCO ENCALADA", "1771"): 1,
    ("BLANCO ENCALADA", "1797"): 2,
    ("EJERCITO", "650"): 3,
    ("EJERCITO", "520"): 4,
    ("TOESCA", "2002"): 5,
    ("ESPANA", "397"): 6,
    ("MORANDE", "707"): 10,
    ("CATEDRAL", "1350"): 11,
    ("SANTO DOMINGO", "756"): 12,
    ("SANTO DOMINGO", "1890"): 13,
    ("LORD COCHRANE", "184"): 14,
    ("LORD COCHRANE", "252"): 15,
    ("SAZIE", "1738"): 16,
    ("SAN IGNACIO", "1498"): 17,
    ("TARAPACA", "1331"): 18,
    ("ALDUNATE", "1525"): 19,
    ("SAN DIEGO", "2381"): 20,
    ("FRANKLIN", "200"): 21,
    ("NATANIEL COX", ""): 22,
    ("SAN FRANCISCO", "467"): 30,
    ("SAN ISIDRO", "96"): 31,
    ("SAN ISIDRO", "379"): 32,
    ("SANTA ISABEL", "326"): 33,
    ("SANTA VICTORIA", "562"): 34,
    ("SANTA ROSA", "991"): 35,
    ("CARMEN", "110"): 36,
    ("VICUNA MACKENNA", "920"): 37,
    ("DIAGONAL VICUNA MACKENNA", "2004"): 38,
}

CATASTRO_COLUMNS = [
    "calle",
    "numero",
    "anio_desde",
    "anio_hasta",
    "confianza",
    "fuente",
]

CATASTRO_ROWS = [
    ("BLANCO ENCALADA", "1771", 2004, 2010, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("BLANCO ENCALADA", "1797", 1998, 2006, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("EJERCITO", "650", 2000, 2010, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("EJERCITO", "520", 1990, 2000, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("TOESCA", "2002", 2014, 2020, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("ESPANA", "397", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("MORANDE", "707", 1990, 2000, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("CATEDRAL", "1350", 1985, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SANTO DOMINGO", "756", 1990, 2000, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SANTO DOMINGO", "1890", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("LORD COCHRANE", "184", 1985, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("LORD COCHRANE", "252", 1990, 2000, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SAZIE", "1738", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SAN IGNACIO", "1498", 1985, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("TARAPACA", "1331", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("ALDUNATE", "1525", 1985, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SAN DIEGO", "2381", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("FRANKLIN", "200", 1990, 2000, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("NATANIEL COX", "", 1980, 1995, "baja", "Estimación referencial DepaFix; sin número en origen"),
    ("SAN FRANCISCO", "467", 1990, 2000, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SAN ISIDRO", "96", 1985, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SAN ISIDRO", "379", 1990, 2000, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SANTA ISABEL", "326", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SANTA VICTORIA", "562", 1985, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("SANTA ROSA", "991", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("CARMEN", "110", 1980, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("VICUNA MACKENNA", "920", 1985, 1995, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
    ("DIAGONAL VICUNA MACKENNA", "2004", 2005, 2015, "media", "Estimación referencial DepaFix; reemplazar por catastro municipal"),
]

GEOCODE_BOUNDS = {
    "lat_min": -33.50,
    "lat_max": -33.40,
    "lon_min": -70.72,
    "lon_max": -70.60,
}

GEOCODE_USER_AGENT = "DepaFix-Operations/1.0 (contact: operations@depafix.cl)"
GEOCODE_DELAY_SECONDS = 1.1
GOOGLE_MAPS_WAYPOINT_LIMIT = 9
