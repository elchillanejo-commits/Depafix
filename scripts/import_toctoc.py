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

UF = 38800


def norm_precio(item):
    """Normaliza precio. Acepta CLP directo o UF."""
    vals = [item.get("precio_peso") or 0, item.get("precio_uf") or 0]
    # CLP directo (100K - 5M)
    for v in vals:
        if 100000 <= v <= 5000000:
            return int(v)
    # UF (3 - 200)
    for v in vals:
        if 3 <= v <= 200:
            return int(v * UF)
    return None


def importar(archivo):
    items = json.loads(Path(archivo).read_text())
    nuevas = 0
    actualizadas = 0
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
            actualizadas += 1
        else:
            client.table("properties").insert(data).execute()
            nuevas += 1
    return nuevas, actualizadas, saltadas


base = Path("/tmp/toctoc-dataset-inmobiliario")
total_n = total_a = total_s = 0
for f in ["depto-arriendo-toctoc.json", "casa-arriendo-toctoc.json"]:
    p = base / f
    if not p.exists():
        print(f"❌ No existe: {p}")
        continue
    n, a, s = importar(str(p))
    total_n += n
    total_a += a
    total_s += s
    print(f"{f}: {n} nuevas, {a} actualizadas, {s} saltadas")

print(f"\n🎯 TOTAL: {total_n} nuevas, {total_a} actualizadas, {total_s} saltadas")
