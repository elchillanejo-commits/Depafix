import re
from pathlib import Path
p = Path("scripts/parsear_grupo.py")
s = p.read_text(encoding="utf-8")
s = s.replace(
    'filas.sort(key=lambda r: -r["mensajes"])',
    'ruido = [r for r in filas if r["mensajes"] < 3]\n    filas = [r for r in filas if r["mensajes"] >= 3]\n    filas.sort(key=lambda r: -r["mensajes"])'
)
s = s.replace(
    'Path("data").mkdir(exist_ok=True)',
    'Path("data").mkdir(exist_ok=True)\n    with open("data/contactos_ruido.csv", "w", encoding="utf-8", newline="") as f:\n        w = csv.DictWriter(f, fieldnames=list(ruido[0].keys()) if ruido else ["nombre_whatsapp","mensajes"])\n        w.writeheader()\n        w.writerows(ruido)'
)
p.write_text(s, encoding="utf-8")
print("Patch main aplicado (filtro ruido + archivo separado)")
