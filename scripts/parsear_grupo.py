#!/usr/bin/env python3
import re, csv
from collections import Counter, defaultdict
from pathlib import Path

CHAT = Path("_chat.txt")
LINE_RE = re.compile(
    r"^\[(\d{2}-\d{2}-\d{2}), (\d{1,2}:\d{2}:\d{2})\s*([ap]\.\s?m\.)\]\s*(.*?):\s?(.*)$",
    re.IGNORECASE,
)

PATRONES = {
    "cronista":       [r"resultado", r"gan[oó]", r"perdi[oó]", r"felicitaciones", r"marcador"],
    "organizador":    [r"form\.gle", r"webpay", r"inscripci[oó]n", r"cierre", r"link de pago", r"programaci[oó]n"],
    "vendedor":       [r"vendo", r"precio", r"despacho", r"interesad", r"\$\s?\d", r"por interno"],
    "analista":       [r"creo que", r"opino", r"en mi opini[oó]n", r"evidencia", r"seg[uú]n"],
    "animador":       [r"jaja", r"sticker", r"jeje"],
    "partner_seeker": [r"partner", r"se cay[oó]", r"alguien para", r"alguien que"],
    "recien_llegado": [r"acabo de entrar", r"nuevo socio", r"me presento", r"reci[eé]n llegado"],
    "comprador":      [r"me anoto", r"pagad[oa]", r"transferencia", r"cu[aá]nto", r"cuanto sale"],
}

PESOS = {
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
    "organizador":    [(r"form\.gle", 3.0), (r"webpay", 3.0), (r"inscripci[oó]n", 2.0),
                       (r"link de pago", 3.0), (r"programaci[oó]n", 2.0), (r"cierre", 1.5)],
    "vendedor":       [(r"vendo", 3.0), (r"despacho", 2.5), (r"\$\s?\d", 2.0),
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


def parse(path):
    msgs, fechas = defaultdict(list), defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        fecha, hora, ampm, autor, texto = m.groups()
        autor = autor.strip()
        if autor in ("Rama de Tenis Stade", "~", "Tú", "Tu", ""):
            continue
        msgs[autor].append(texto)
        fechas[autor].append(fecha)
    return msgs, fechas

def main():
    if not CHAT.exists():
        print("ERROR: _chat.txt no existe en", CHAT.resolve())
        return 1
    msgs, fechas = parse(CHAT)
    if not msgs:
        print("ERROR: no se parseo ningun mensaje. Revisa _chat.txt")
        return 1
    filas = []
    for autor, m in msgs.items():
        filas.append({
            "nombre_whatsapp":         autor,
            "es_socio_stade":          "SF" in autor,
            "mensajes":                len(m),
            "primer_mensaje":          fechas[autor][0],
            "ultimo_mensaje":          fechas[autor][-1],
            "arquetipo_dominante":     clasificar(m),
            "consentimiento_contacto": "NO",
            "fuente":                  "grupo_rama_tenis_2026",
        })
    ruido = [r for r in filas if r["mensajes"] < 3]
    filas = [r for r in filas if r["mensajes"] >= 3]
    filas.sort(key=lambda r: -r["mensajes"])
    Path("data").mkdir(exist_ok=True)
    with open("data/contactos_ruido.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ruido[0].keys()) if ruido else ["nombre_whatsapp","mensajes"])
        w.writeheader()
        w.writerows(ruido)
    with open("data/contactos_grupo.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print("OK: %d contactos -> data/contactos_grupo.csv" % len(filas))
    print("Socios SF:", sum(1 for r in filas if r["es_socio_stade"]))
    print("Arquetipos:", Counter(r["arquetipo_dominante"] for r in filas).most_common())
    print("\nTop 15 mas activos:")
    for r in filas[:15]:
        print("  %4d  %-38s  %s" % (r["mensajes"], r["nombre_whatsapp"][:38], r["arquetipo_dominante"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
