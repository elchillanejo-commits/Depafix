#!/usr/bin/env python3
# test_agente.py - QA de ingesta de cursos SENCE (DepaFix)
# Requisitos: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en entorno/.env.
# Cero valores fijos de credenciales ni datos duros en el codigo.

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# Carga .env local si existe (sin depender de que el usuario exporte variables)
env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
TABLE = os.getenv("DEPAFIX_TABLA", "cursos_sence")
INGESTOR = os.getenv("DEPAFIX_INGESTOR", "crear_curso_sence.py")
REPORT = "REPORTE_PRUEBAS.md"


def main():
    if len(sys.argv) < 2:
        print("Uso: python test_agente.py <ruta_pdf>")
        sys.exit(1)

    pdf = sys.argv[1]
    if not os.path.isfile(pdf):
        print(f"PDF no encontrado: {pdf}")
        sys.exit(1)

    t0 = time.time()
    errores = []
    insertado = False
    codigo = None

    # 1. Ejecutar ingestor con el PDF (bandera --archivo, no argumento posicional)
    try:
        res = subprocess.run(
            [sys.executable, INGESTOR, "--archivo", pdf, "--estado", "borrador"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(BASE_DIR),
        )
        # stdout trae JSON del curso; extraer codigo_sence
        try:
            data = json.loads(res.stdout) or {}
            codigo = data.get("codigo_sence")
        except Exception:
            # fallback: buscar en texto plano
            import re as _re
            m = _re.search(r'codigo_sence"\s*:\s*"?(\d{6,10})"?', res.stdout)
            if m:
                codigo = m.group(1)
    except FileNotFoundError:
        errores.append(f"Ingestor no encontrado: {INGESTOR}")
    except subprocess.CalledProcessError as e:
        errores.append(f"Ingestor fallo (exit {e.returncode}): {(e.stderr or '').strip()[:400]}")
    except Exception as e:
        errores.append(f"Error ejecutando ingestor: {e}")

    # 2. Verificar insercion en Supabase via REST (sin dependencias pesadas)
    if not errores and SUPABASE_URL and SUPABASE_KEY:
        try:
            filtro = f"?codigo_sence=eq.{codigo}" if codigo else f"?origen_archivo=eq.{os.path.basename(pdf)}"
            url = f"{SUPABASE_URL}/rest/v1/{TABLE}{filtro}&select=codigo_sence"
            req = urllib.request.Request(
                url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                datos = json.loads(r.read().decode() or "[]")
                insertado = len(datos) > 0
        except Exception as e:
            errores.append(f"Error verificando Supabase: {e}")
    elif not errores:
        errores.append("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY en el entorno")

    elapsed = time.time() - t0
    estado = "INSERTADO" if insertado else "NO INSERTADO"

    lineas = [
        "# Reporte de Prueba - Ingesta",
        f"- Archivo probado: {pdf}",
        f"- Estado: {estado}",
        f"- Codigo SENCE detectado: {codigo or 'N/A'}",
        f"- Tiempo de ejecucion: {elapsed:.2f} s",
        f"- Errores: {'; '.join(errores) if errores else 'Ninguno'}",
    ]
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")

    print("\n".join(lineas))
    sys.exit(0 if insertado else 1)


if __name__ == "__main__":
    main()
