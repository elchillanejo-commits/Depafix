"""Importa dataset TocToc con filtros realistas para arriendo."""
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

UF = 38800
# Rangos realistas para arriendo Chile
MIN_CLP = 200_000
MAX_CLP = 8_000_000
MIN_UF = 5
MAX_UF = 200


def norm_precio(item):
    """Normaliza precio. Solo acepta valores realistas de arriendo."""
    vals = [item.get("precio_peso") or 0, item.get("precio_uf") or 0]
    # CLP directo
    for v in vals:
        if MIN_CLP <= v <= MAX_CLP:
            return int(v)
    # UF (solo si el resultado cae en rango CLP realista)
    for v in vals:
        if MIN_UF <= v <= MAX_UF:
            clp = int(v * UF)
            if MIN_CLP <= clp <= MAX_CLP:
                return clp
    return None


def importar(archivo):
    items = json.loads(Path(archivo).read_text())
    nuevas = 0
    saltadas = 0
    for it in items:
        precio = norm_precio(it)
        if not precio:
            saltadas += 1
            continue
        sid = f"toctoc-{it['id']}"
        m2 = int(it.get("m2_superficie") or 0) or None
        data = {
            "source_id": sid,
            "source_portal": "toctoc",
            "titulo": (it.get("titulo") or "")[:200],
            "precio_clp": precio,
            "precio_m2": int(precio / m2) if m2 else None,
            "dormitorios": it.get("dormitorios"),
            "banos": it.get("baños"),
            "m2": m2,
            "comuna": it.get("comuna") or "",
            "direccion": it.get("direccion") or "",
            "url": it.get("url") or "",
            "imagen_url": it.get("imagen") or None,
            "activa": True,
            "ultimo_scrape": datetime.now(timezone.utc).isoformat(),
        }
        ex = (
            client.table("properties")
            .select("id")
            .eq("source_id", sid)
            .limit(1)
            .execute()
        )
        if ex.data:
            client.table("properties").update(data).eq("source_id", sid).execute()
        else:
            client.table("properties").insert(data).execute()
            nuevas += 1
    return nuevas, saltadas


# 1. LIMPIAR properties con precios irreales
print("🧹 Limpiando precios irreales...")
r = client.table("properties").select("id,precio_clp").execute()
borrar = [p["id"] for p in r.data if p.get("precio_clp") and (p["precio_clp"] < MIN_CLP or p["precio_clp"] > MAX_CLP)]
if borrar:
    client.table("properties").delete().in_("id", borrar).execute()
    print(f"  Eliminadas {len(borrar)} props con precios irreales")

# 2. RE-IMPORTAR limpio
base = Path("/tmp/toctoc-dataset-inmobiliario")
total_n = total_s = 0
for f in ["depto-arriendo-toctoc.json", "casa-arriendo-toctoc.json"]:
    p = base / f
    if not p.exists():
        continue
    n, s = importar(str(p))
    total_n += n
    total_s += s
    print(f"{f}: {n} nuevas, {s} saltadas")

print(f"\n✅ TOTAL: {total_n} nuevas cargadas")

# 3. VERIFICAR
r2 = client.table("properties").select("id", count="exact").execute()
print(f"\n📊 Total en Supabase: {r2.count}")
