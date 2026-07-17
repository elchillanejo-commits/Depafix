#!/usr/bin/env python3
"""
test_connectivity.py -- smoke test de conectividad: confirma que las
credenciales de .env sirven para hablar con Supabase de verdad, sin asumir
nada sobre tablas de negocio que no se pudieron confirmar en el repo.

Corre con pytest si está instalado (pip install pytest), pero también corre
como script plano -- no depende de pytest para que sirva de smoke test
inmediato en cualquier terminal:

    python3 tests/test_connectivity.py

Qué prueba (duro, falla el smoke test si algo de esto rompe):
    1. config.settings.BASE_DIR se importa y apunta a una carpeta real.
    2. DatabaseManager.get_client() conecta con las credenciales de .env.
    3. Se puede leer (SELECT) de una tabla CONFIRMADA en supabase_schema.sql
       (user_keys) -- confirma que la conexión sirve para I/O real, no solo
       que el cliente se construyó.

Qué prueba (blando, solo avisa):
    4. Lectura de la tabla de negocio (TABLA_NEGOCIO). Por default apunta a
       "presupuestos" -- "presupuestos_generados" (el nombre pedido
       originalmente) NO existe: PostgREST devuelve PGRST205 y sugiere
       "presupuestos" (verificado en vivo 2026-07-16). Si esto falla, es
       información -- no hace fallar el smoke test de conectividad.
"""
import sys
import traceback
from pathlib import Path

CORE_PATH = Path(__file__).resolve().parent.parent
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from config.settings import BASE_DIR
from core.db_manager import DatabaseManager

TABLA_CONFIRMADA = "user_keys"   # existe en supabase_schema.sql, verificado 2026-07-12
TABLA_NEGOCIO = "presupuestos"   # nombre real; "presupuestos_generados" no existe (ver bi_exporter.py)


def test_base_dir():
    assert BASE_DIR.exists(), f"BASE_DIR no existe en disco: {BASE_DIR}"


def test_conexion_supabase():
    client = DatabaseManager.get_client()
    assert client is not None


def test_lectura_tabla_confirmada():
    client = DatabaseManager.get_client()
    resp = client.table(TABLA_CONFIRMADA).select("*").limit(1).execute()
    assert isinstance(resp.data, list)


def _chequeo_blando_tabla_negocio():
    """No es un test estricto: informa si la tabla de negocio existe, sin
    hacer fallar el smoke test por algo que ya sabemos que no está confirmado."""
    try:
        client = DatabaseManager.get_client()
        resp = client.table(TABLA_NEGOCIO).select("*").limit(1).execute()
        return True, f"'{TABLA_NEGOCIO}' respondió {len(resp.data)} fila(s)."
    except Exception as e:
        return False, f"'{TABLA_NEGOCIO}' no accesible: {e}"


def _correr_como_script():
    pruebas = [
        ("BASE_DIR importable", test_base_dir),
        ("Conexión a Supabase (anon)", test_conexion_supabase),
        (f"Lectura de tabla confirmada ({TABLA_CONFIRMADA})", test_lectura_tabla_confirmada),
    ]

    fallas = 0
    for nombre, fn in pruebas:
        try:
            fn()
            print(f"[OK]   {nombre}")
        except Exception:
            fallas += 1
            print(f"[FAIL] {nombre}")
            print(traceback.format_exc())

    ok_negocio, mensaje_negocio = _chequeo_blando_tabla_negocio()
    print(f"[{'OK' if ok_negocio else 'INFO'}]   Tabla de negocio: {mensaje_negocio}")

    print()
    if fallas:
        print(f"RESULTADO: {fallas} chequeo(s) crítico(s) fallaron. Revisa .env / RLS / red.")
        sys.exit(1)
    print("RESULTADO: conectividad OK. La tabla de negocio es informativa (ver mensaje arriba).")
    sys.exit(0)


if __name__ == "__main__":
    _correr_como_script()
