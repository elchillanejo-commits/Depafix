import csv
from pathlib import Path

path = Path("data/speeches.csv")
headers = ["id", "prospecto_id", "fecha", "eneatipo", "rubro", "texto", "estado", "fuente", "consentimiento"]

abogado_text = """Hola, ¿cómo estás? Te escribo de par a par, fuera de la cancha. Quiero proponerte una Auditoría Express de 15 min para revisar las consultas que podrían perderse por responder tarde.

Te muestro cómo la IA puede dar la primera respuesta, clasificar casos y agendar llamadas, con confidencialidad y ética profesional. Terminas con un diagnóstico en una página, sin cambiar nada todavía.

¿Te acomoda un café en el club esta semana? Es sin compromiso; si no es prioridad, un "no ahora" está perfecto."""

# Versión Claude Haiku 5.5
construccion_text = """Ibar, en una licitación un anexo mal cuadrado o una GSO mal emitida te saca antes de que compitan los precios. Propongo revisar una licitación real tuya, con bases, anexos y GSO, en unos 20 minutos. No te prometo encontrar un problema; te prometo revisar los tres documentos y decirte con precisión qué encontramos y qué no.

Si al terminar no hay nada que corregir, lo dices tú y cerramos sin problema. Si hay algo, te dejo por escrito qué es y qué haría primero, aunque no sigamos trabajando juntos. Si me compartes la licitación con 24 horas de anticipación, llego con el cruce hecho.

¿Te acomoda el viernes 30 a las 9:30 o el jueves 5 de noviembre a las 16:00?"""

rows = [
    ["S_ABOG_001", "P_ABOGADO_001", "2026-10-29", "3w2", "abogado", abogado_text, "aprobado", "lista_300", "SÍ"],
    ["S_CONSTR_001", "P_CONSTR_001", "2026-10-29", "8w7", "construccion", construccion_text, "aprobado", "lista_300", "SÍ"]
]

with open(path, mode="w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(rows)

print(f"OK: Speech de Claude guardado en {path}")
