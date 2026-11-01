import csv
from pathlib import Path

path = Path("data/speeches.csv")
headers = ["id", "prospecto_id", "fecha", "eneatipo", "rubro", "texto", "estado", "fuente", "consentimiento"]

# El speech exacto que generó el Agente (Aire - Copywriting)
tenis_text = """Como somos del mismo club, te ahorro el discurso de ventas. Sé que organizar la Laver Cup o la Copa Italia es un culo con las inscripciones. Te propongo automatizar el cobro (Webpay) y la lista de inscritos con un link que hace todo solo.

Tú mandas el link, el jugador paga y queda inscrito al instante. Se acabó perseguir transferencias, confirmar pagos a mano o actualizar el Excel a las 2 de la mañana. La lista se llena sola y tú ves en tiempo real quién pagó y quién no, sin errores de cuadre.

¿Te muestro cómo funciona en 10 min el jueves?"""

rows = [
    ["S_TENIS_001", "P_STADE_ORG", "2026-10-31", "3w2", "tenis", tenis_text, "aprobado", "grupo_rama", "SÍ"]
]

file_exists = path.exists()

with open(path, mode="a", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(headers)
    writer.writerows(rows)

print(f"OK: Speech de Tenis guardado en {path}")
