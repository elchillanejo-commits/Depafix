import csv
from pathlib import Path

path = Path("data/speeches.csv")
headers = ["id", "prospecto_id", "fecha", "eneatipo", "rubro", "texto", "estado", "fuente", "consentimiento"]

abogado_text = """Hola, ¿cómo estás? Te escribo de par a par, fuera de la cancha. Quiero proponerte una Auditoría Express de 15 min para revisar las consultas que podrían perderse por responder tarde.

Te muestro cómo la IA puede dar la primera respuesta, clasificar casos y agendar llamadas, con confidencialidad y ética profesional. Terminas con un diagnóstico en una página, sin cambiar nada todavía.

¿Te acomoda un café en el club esta semana? Es sin compromiso; si no es prioridad, un "no ahora" está perfecto."""

construccion_text = """Te escribo directo: en construcción, muchas licitaciones se caen en la evaluación administrativa por errores en los anexos; el precio también pesa, pero un error formal te saca antes de competir. Revisar bases administrativas, bases técnicas, anexos y la garantía de seriedad (boleta) a mano te come horas, y una firma mal puesta te deja fuera.

Por eso armé una Auditoría Express de 20 min: revisamos una licitación real tuya en vivo, detectamos inconsistencias en los anexos y revisamos si las modificaciones en ChileCompra cambian las bases antes del cierre. No reemplaza tu juicio: reduce el riesgo de caer por un documento o una firma.

¿Te hace sentido una auditoría express esta semana para reforzar tus postulaciones? Vamos al grano. Si al minuto 10 no te convence, lo cerramos y listo. Tú decides."""

rows = [
    ["S_ABOG_001", "P_ABOGADO_001", "2026-10-29", "3w2", "abogado", abogado_text, "aprobado", "lista_300", "SÍ"],
    ["S_CONSTR_001", "P_CONSTR_001", "2026-10-29", "8w7", "construccion", construccion_text, "aprobado", "lista_300", "SÍ"]
]

file_exists = path.exists()

with open(path, mode="a", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(headers)
    writer.writerows(rows)

print(f"OK: {len(rows)} speeches guardados en {path}")
print(f"Total lineas en el archivo: {sum(1 for _ in open(path, encoding='utf-8'))}")
