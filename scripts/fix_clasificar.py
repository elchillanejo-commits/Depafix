import re
from pathlib import Path

p = Path("scripts/parsear_grupo.py")
s = p.read_text(encoding="utf-8")

nuevo_clasificar = '''PESOS = {
    "organizador":    3.0,
    "vendedor":       2.0,
    "analista":       2.0,
    "cronista":       1.0,
    "comprador":      1.5,
    "partner_seeker": 1.0,
    "recien_llegado": 2.0,
    "animador":       0.5,
}

PATRONES_PESADOS = {
    "organizador":    [(r"form\\\\.gle", 3.0), (r"webpay", 3.0), (r"inscripci[oó]n", 2.0),
                       (r"link de pago", 3.0), (r"programaci[oó]n", 2.0), (r"cierre", 1.5)],
    "vendedor":       [(r"vendo", 3.0), (r"despacho", 2.5), (r"\\\\$\\\\s?\\\\d", 2.0),
                       (r"interesad", 1.5), (r"por interno", 1.0)],
    "analista":       [(r"en mi opini[oó]n", 2.5), (r"evidencia", 2.5), (r"creo que", 1.0),
                       (r"opino", 1.5), (r"seg[uú]n", 1.0)],
    "cronista":       [(r"marcador", 2.0), (r"resultado", 1.5), (r"gan[oó]", 0.8),
                       (r"perdi[oó]", 0.8), (r"felicitaciones", 0.3)],
    "comprador":      [(r"me anoto", 2.0), (r"pagad[oa]", 2.0), (r"transferencia", 1.5),
                       (r"cu[aá]nto", 1.0)],
    "partner_seeker": [(r"se cay[oó]", 2.0), (r"alguien para", 1.5), (r"partner", 1.0)],
    "recien_llegado": [(r"acabo de entrar", 3.0), (r"nuevo socio", 2.5), (r"me presento", 2.5)],
    "animador":       [(r"jaja", 0.3), (r"sticker", 0.3), (r"jeje", 0.3)],
}

PRIORIDAD = ["organizador", "vendedor", "analista", "cronista", "comprador",
             "partner_seeker", "recien_llegado", "animador"]

def clasificar(mensajes):
    texto = " ".join(mensajes).lower()
    scores = {}
    for arq, pats in PATRONES_PESADOS.items():
        total = 0.0
        for p, w in pats:
            total += len(re.findall(p, texto)) * w
        scores[arq] = round(total, 1)
    max_score = max(scores.values()) if scores else 0
    if max_score < 3.0:
        return "indefinido"
    ganadores = [a for a, s in scores.items() if s == max_score]
    for a in PRIORIDAD:
        if a in ganadores:
            return a
    return "indefinido"
'''

s = re.sub(r"def clasificar\(mensajes\):.*?return scores\.most_common\(1\)\[0\]\[0\] if scores else \"indefinido\"",
           nuevo_clasificar, s, count=1, flags=re.S)
p.write_text(s, encoding="utf-8")
print("Patch aplicado a clasificar()")
