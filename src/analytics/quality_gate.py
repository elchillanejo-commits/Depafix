"""
quality_gate.py -- valida y limpia data/inmo_data.csv (bruto, acumulado por
src/agents/inmo_scrapper.py en modo append) e inyecta SOLO las filas nuevas
y válidas en data/inmo_data_clean.csv -- nunca sobreescribe el archivo
limpio, para que Power BI pueda hacer series de tiempo sobre el histórico
completo (ver docs/05_GUIA_CONEXION_POWERBI.md).

Cómo queda "incremental" sin necesitar un archivo de checkpoint aparte: el
propio inmo_data_clean.csv ya es el estado -- en cada corrida se relee
completo, se calcula qué filas del bruto ya están representadas ahí (por la
clave de duplicado de abajo) y solo se hace APPEND de las que faltan. Correr
esto dos veces seguidas sobre el mismo bruto es seguro (idempotente): la
segunda vez no agrega nada.

Regla de duplicado: misma propiedad (titulo) + mismo precio + mismo día
(fecha truncada a fecha, sin hora) ya presente en inmo_data_clean.csv se
descarta -- evita que corridas repetidas del scraper en el mismo día sin
cambio de precio infle el histórico con filas idénticas. Un cambio de
precio, o un día distinto, sí genera una fila nueva -- eso es precisamente
la serie de tiempo que Aquiles necesita en Power BI.

LIMITACIÓN CONOCIDA: 'titulo' es el único identificador de propiedad que
expone hoy src/agents/inmo_scrapper.py -- dos propiedades distintas con el
mismo título literal se tratarían como la misma. Si el scraper real llega a
capturar una URL o ID de listing, hay que usarlo como clave en vez de
'titulo' (cambiar solo _clave_duplicado).
"""
import sys
from pathlib import Path

CORE_PATH = Path(__file__).resolve().parent.parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

import pandas as pd
from config.settings import BASE_DIR

ARCHIVO_BRUTO = BASE_DIR / 'data' / 'inmo_data.csv'
ARCHIVO_LIMPIO = BASE_DIR / 'data' / 'inmo_data_clean.csv'

COLUMNAS_REQUERIDAS = ['titulo', 'precio', 'fecha']


def _cargar_bruto():
    df = pd.read_csv(ARCHIVO_BRUTO)
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Columnas requeridas faltantes en {ARCHIVO_BRUTO.name}: {faltantes}")
    return df


def _validar_calidad(df):
    """Descarta filas con precio inválido o campos vacíos -- no lanza, para
    que un dato corrupto no aborte el resto del gate."""
    antes = len(df)
    df = df.dropna(subset=COLUMNAS_REQUERIDAS)
    df = df[df['precio'] > 0]
    df = df[df['titulo'].astype(str).str.strip() != '']
    return df, antes - len(df)


def _clave_duplicado(df):
    """titulo (normalizado) + precio + día -- ver docstring del módulo."""
    fecha_dt = pd.to_datetime(df['fecha'], errors='coerce')
    return (
        df['titulo'].astype(str).str.strip().str.lower()
        + '|' + df['precio'].astype(str)
        + '|' + fecha_dt.dt.date.astype(str)
    )


def gate_keeper():
    try:
        df_bruto = _cargar_bruto()
    except Exception as e:
        print(f"[ERROR] No se pudo leer el archivo bruto: {e}")
        return 0, 0

    df_valido, descartadas_calidad = _validar_calidad(df_bruto)
    if descartadas_calidad:
        print(f"[GATE] {descartadas_calidad} fila(s) descartada(s) por precio/campos inválidos.")

    if ARCHIVO_LIMPIO.exists():
        claves_existentes = set(_clave_duplicado(pd.read_csv(ARCHIVO_LIMPIO)))
    else:
        claves_existentes = set()

    df_valido = df_valido.copy()
    df_valido['_clave'] = _clave_duplicado(df_valido)
    df_nuevas = df_valido[~df_valido['_clave'].isin(claves_existentes)].drop(columns=['_clave'])

    duplicadas = len(df_valido) - len(df_nuevas)
    if duplicadas:
        print(f"[GATE] {duplicadas} fila(s) descartada(s) por duplicado (misma propiedad/precio/día).")

    if df_nuevas.empty:
        print("[GATE] Sin filas nuevas que agregar. inmo_data_clean.csv sin cambios.")
        return 0, descartadas_calidad + duplicadas

    escribir_header = not ARCHIVO_LIMPIO.exists()
    df_nuevas.to_csv(ARCHIVO_LIMPIO, mode='a', header=escribir_header, index=False)
    print(f"[GATE] Calidad aprobada: {len(df_nuevas)} fila(s) nueva(s) agregada(s) a "
          f"{ARCHIVO_LIMPIO.name} (incremental, histórico preservado).")
    return len(df_nuevas), descartadas_calidad + duplicadas


if __name__ == "__main__":
    gate_keeper()
