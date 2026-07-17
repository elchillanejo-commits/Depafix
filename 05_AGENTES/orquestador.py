#!/usr/bin/env python3
import sys
from pathlib import Path
# Añadir core al path para importar db_manager
sys.path.insert(0, str(Path(__file__).parent / "core"))

try:
    from db_manager import db
    print("🧪 DepaFix - Orquestador")
    result = db.execute("SELECT 1")
    print("✅ Conexión a BD exitosa.")
except Exception as e:
    print(f"❌ Error al importar o conectar: {e}")
    sys.exit(1)
