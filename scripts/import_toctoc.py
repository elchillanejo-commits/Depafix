"""Importa dataset TocToc a tabla properties."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path.home() / "PROYECTOS/Proyectos/DepaFix/.env")
client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
)

UF_CLP = 38800  # UF de referencia 2026

def normalizar_precio(prop: dict) -> int:
    """Detecta si el precio está en UF o CLP y lo normaliza a CLP."""
    precio_peso = prop.get("precio_peso") or 0
    precio_uf = prop.get("precio_uf") or 0

    # Si precio_peso < 10000, probablemente es UF
    if 0 < precio_peso < 10000:
        return int(precio_peso * UF_CLP)
    if precio_peso >= 10000:
        return int(precio_peso)

    # Fallback: usar precio_uf (que también puede estar invertido)
    if precio_uf > 100000:
        return int(precio_uf)
    if 0 < precio_uf < 10000:
        return int(precio_uf * UF_CLP)

    return 0

def importar(archivo: str, tipo: str):
    print(f"\n📂 Importando {archivo}...")
    with open(archivo) as f:
        props = json.load(f)

    print(f"   Total: {len(props)} propiedades")

    nuevas = 0
    actualizadas = 0
    saltadas = 0

    for p in props:
        try:
            precio = normalizar_precio(p)
            if precio <= 0:
                saltadas += 1
                continue

            source_id = f"toctoc-{p['id']}"
            m2 = int(p.get("m2_superficie") or 0) or None
            precio_m2 = int(precio / m2) if m2 and m2 > 0 else None

            # Fecha
            fecha_str = p.get("fecha_publicacion") or ""
            try:
                fecha = datetime.strptime(fecha_str, "%d-%m-%Y %H:%M:%S").isoformat()
            except:
                fecha = None

            data = {
                "source_id": source_id,
                "source_portal": "toctoc",
                "titulo": (p.get("titulo") or "")[:200],
                "precio_clp": precio,
                "precio_m2": precio_m2,
                "dormitorios": p.get("dormitorios"),
                "banos": p.get("baños"),
                "m2": m2,
                "direccion": "",
                "comuna": p.get("comuna") or "",
                "url": p.get("url") or "",
                "imagen_url": p.get("imagen") or None,
                "activa": True,
                "fecha_publicacion": fecha,
                "ultimo_scrape": datetime.now(timezone.utc).isoformat(),
            }

            existing = client.table("properties").select("id").eq("source_id", source_id).limit(1).execute()
            if existing.data:
                client.table("properties").update({
                    "precio_clp": precio,
                    "precio_m2": precio_m2,
                    "ultimo_scrape": data["ultimo_scrape"],
                }).eq("source_id", source_id).execute()
                actualizadas += 1
            else:
                client.table("properties").insert(data).execute()
                nuevas += 1

        except Exception as e:
            print(f"   ⚠️ Error en {p.get('id')}: {str(e)[:100]}")
            saltadas += 1

    print(f"   ✅ Nuevas: {nuevas} | Actualizadas: {actualizadas} | Saltadas: {saltadas}")
    return nuevas, actualizadas

# Ejecutar para arriendos deptos y casas
base = Path("/tmp/toctoc-dataset-inmobiliario")
total_n = total_a = 0

for archivo, tipo in [
    (base / "depto-arriendo-toctoc.json", "departamento"),
    (base / "casa-arriendo-toctoc.json", "casa"),
]:
    if archivo.exists():
        n, a = importar(str(archivo), tipo)
        total_n += n
        total_a += a

print(f"\n🎯 TOTAL: {total_n} nuevas, {total_a} actualizadas")
