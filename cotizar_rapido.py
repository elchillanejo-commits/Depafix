#!/usr/bin/env python3
"""
cotizar_rapido.py
Script maestro interactivo para generar presupuestos de subcontrato.
Pide los 5 datos por consola y ejecuta procesar_subcontrato.py internamente.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

def pedir_dato(prompt: str, default: str = "") -> str:
    """Pide un dato por consola. Reintenta si queda vacío (salvo que haya default)."""
    while True:
        valor = input(f"{prompt}: ").strip()
        if valor:
            return valor
        if default:
            print(f"  (usando valor por defecto: {default})")
            return default
        print("  ⚠️  Este campo es obligatorio. Intenta de nuevo.")

def validar_pdf(ruta_str: str) -> Path:
    """Verifica que el PDF exista y tenga extensión .pdf."""
    ruta = Path(ruta_str).expanduser().resolve()
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    if not ruta.is_file():
        raise IsADirectoryError(f"La ruta no es un archivo: {ruta}")
    if ruta.suffix.lower() != ".pdf":
        raise ValueError(f"El archivo no parece ser un PDF: {ruta.name}")
    return ruta

def validar_fecha(fecha_str: str) -> str:
    """Valida formato YYYY-MM-DD."""
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return fecha_str
    except ValueError:
        raise ValueError(f"Fecha inválida '{fecha_str}'. Formato esperado: YYYY-MM-DD")

def main() -> int:
    print("=" * 60)
    print("  COTIZADOR RÁPIDO - DepaFix")
    print("=" * 60)
    print("Ingresa los datos para procesar el PDF del contratista.\n")

    try:
        # 1. Ruta del PDF
        ruta_pdf_input = pedir_dato("📄 Ruta del PDF del contratista")
        ruta_pdf = validar_pdf(ruta_pdf_input)

        # 2. Código de proyecto
        proyecto = pedir_dato("🏗️  Código de proyecto (ej. Macul_Ñuñoa_001)")

        # 3. Proveedor
        proveedor = pedir_dato("🏢 Nombre del proveedor")

        # 4. Prefijo SKU
        sku_prefix = pedir_dato("🔖 Prefijo SKU (ej. CER)")

        # 5. Fecha requerida
        fecha_input = pedir_dato("📅 Fecha requerida (YYYY-MM-DD)")
        fecha = validar_fecha(fecha_input)

    except (FileNotFoundError, IsADirectoryError, ValueError) as e:
        print(f"\n❌ Error en los datos ingresados: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n\n⏹️  Operación cancelada por el usuario.")
        return 130

    # Mostrar resumen antes de ejecutar
    print("\n" + "-" * 60)
    print("Resumen de la operación:")
    print(f"  PDF:        {ruta_pdf}")
    print(f"  Proyecto:   {proyecto}")
    print(f"  Proveedor:  {proveedor}")
    print(f"  SKU prefix: {sku_prefix}")
    print(f"  Fecha:      {fecha}")
    print("-" * 60)

    confirm = input("¿Ejecutar? [S/n]: ").strip().lower()
    if confirm and confirm not in ("s", "si", "sí", "y", "yes"):
        print("⏹️  Cancelado.")
        return 0

    # Construir comando
    script_dir = Path(__file__).parent.resolve()
    script_procesar = script_dir / "procesar_subcontrato.py"

    if not script_procesar.exists():
        print(f"\n❌ No se encontró procesar_subcontrato.py en: {script_dir}")
        return 1

    cmd = [
        sys.executable,
        str(script_procesar),
        "--pdf", str(ruta_pdf),
        "--proyecto", proyecto,
        "--proveedor", proveedor,
        "--sku-prefix", sku_prefix,
        "--fecha-requerida", fecha,
    ]

    print("\n🚀 Ejecutando procesar_subcontrato.py...\n")

    try:
        resultado = subprocess.run(
            cmd,
            cwd=str(script_dir),
            capture_output=False,   # deja ver el output en vivo
            text=True,
        )
    except FileNotFoundError:
        print(f"\n❌ No se pudo ejecutar Python: {sys.executable}")
        return 1
    except KeyboardInterrupt:
        print("\n\n⏹️  Proceso interrumpido.")
        return 130

    if resultado.returncode != 0:
        print(f"\n❌ procesar_subcontrato.py terminó con código {resultado.returncode}.")
        print("   Revisa los mensajes de error anteriores.")
        return resultado.returncode

    # Mensaje final: intentar ubicar el PDF generado
    # Heurística: buscar el PDF más reciente en la carpeta del proyecto o en ./output
    pdf_generado = None
    candidatos_dirs = [
        script_dir / "output",
        script_dir,
        Path.home() / "DepaFix_Maestro" / "output",
    ]
    pdfs = []
    for d in candidatos_dirs:
        if d.exists() and d.is_dir():
            pdfs.extend(d.glob("*.pdf"))

    if pdfs:
        pdf_generado = max(pdfs, key=lambda p: p.stat().st_mtime)

    print("\n" + "=" * 60)
    if pdf_generado:
        print(f"✅ Presupuesto generado en {pdf_generado}")
    else:
        print("✅ Presupuesto generado. (No se pudo detectar automáticamente la ruta del PDF final.)")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())
