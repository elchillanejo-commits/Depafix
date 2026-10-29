#!/usr/bin/env python3
# agente_ceo_batch.py — IKKI / DepaFix_Maestro
import csv, json, re, sys
from pathlib import Path

RUBRO_ENEATIPO = [
    (r"ceo|gerente general|director|fundador|presidente|due[nñ]o|socio", "8"),
    (r"marketing|publici|creativ|dise|arte|coach|terapeut|foto|musica", "4"),
    (r"salud|medic|enfermer|kine|nutri|educa|colegio|universi|ong|social|psico", "2"),
    (r"legal|abogad|juridic|jurid|auditor|contab|finanz|tesorer|qa|calidad|ingenier|normativ", "1"),
    (r"tecno|software|datos|data|investig|analist|bi|ciencia|dev", "5"),
    (r"operacion|logistic|bodega|transporte|riesgo|seguridad|proceso|planta", "6"),
    (r"innova|emprend|consultor|estrateg|startup|producto|growth", "7"),
    (r"admin|rrhh|recurso humano|atenci[oó]n|cliente|secretari|asistente", "9"),
    (r"venta|comercial|retail|seguro|inmobiliar|corretaje|tienda|ecommerce", "3"),
]

SPEECH = {
 "1": "Hola {n}, se que en {r} el estandar no se negocia. Te propongo un chequeo de 20 min con checklist y un ajuste en 72h, sin tocar tus procesos. Te lo envio?",
 "2": "Hola {n}, en {r} la confianza lo es todo. Te comparto una guia breve para que tu equipo o cliente sienta el cuidado en cada contacto. Te la mando?",
 "3": "Hola {n}, vi tu trabajo en {r}. Te propongo un quick win de 72h con resultado visible para presentar arriba. Te paso un ejemplo de 2 min?",
 "4": "Hola {n}, en {r} lo distinto vende. Te mando una idea de diferenciacion con identidad propia para probar esta semana. La revisamos?",
 "5": "Hola {n}, te dejo un mini-diagnostico con datos de {r} y 3 hipotesis a validar. Sin ruido, solo evidencia. Te lo envio?",
 "6": "Hola {n}, en {r} lo que importa es que no falle. Te propongo un plan de contingencia simple con puntos de control. Lo vemos 20 min?",
 "7": "Hola {n}, en {r} hay una jugada poco explorada que te abre opciones nuevas. Te mando el mapa en 1 pagina. Te sirve?",
 "8": "Hola {n}, en {r} el cuello de botella suele ser la decision, no la ejecucion. Te traigo 2 caminos con impacto y riesgo medido. Agendamos?",
 "9": "Hola {n}, se que en {r} la armonia del equipo pesa. Te propongo un ajuste simple que ordene sin conflictos. Te lo comparto?",
}

SOLUCION = [
    (r"venta|comercial|retail|seguro|inmobiliar|ecommerce|tienda", "Embudo express: 3 quick wins de conversion en 72h + tablero de seguimiento."),
    (r"salud|medic|educa|colegio|universi|ong|psico", "Circuito de agenda y recordatorios: menos ausencias, mas continuidad en 72h."),
    (r"legal|contab|auditor|finanz|qa|calidad", "Checklist de control y matriz de riesgos en 1 pagina, lista en 72h."),
    (r"tecno|software|datos|investig|dev|bi", "Diagnostico tecnico con demo guiada de 20 min y roadmap de 72h."),
    (r"operacion|logistic|transporte|planta|bodega", "Mapeo de cuello de botella y plan de contingencia operativo en 72h."),
    (r"marketing|dise|creativ|publici|producto|growth", "Kit de campana: concepto, 3 piezas y metrica de validacion en 72h."),
    (r"admin|rrhh|atencion|cliente|secretari|asistente", "Plantilla de respuestas y flujo de atencion en 1 pagina, lista en 72h."),
]

def inferir(rubro, edad):
    r = (rubro or "").lower().strip()
    e, conf = "3", "baja"
    for patron, tipo in RUBRO_ENEATIPO:
        if re.search(patron, r):
            e, conf = tipo, "media"
            break
    if edad:
        try:
            ed = int(edad)
            if ed >= 50 and e in {"3", "7", "4"}:
                e, conf = "1", "media"
            if ed < 28 and e in {"1", "6"}:
                e, conf = "3", "media"
        except ValueError:
            pass
    if not r:
        conf = "baja"
    return e, conf

def solucion(rubro):
    r = (rubro or "").lower()
    for p, s in SOLUCION:
        if re.search(p, r):
            return s
    return "Diagnostico express de 20 min + quick win en 72h + propuesta de 1 pagina."

def procesar(fila):
    n  = (fila.get("nombre") or "").strip()
    r  = (fila.get("rubro")  or "").strip()
    ed = (fila.get("edad")   or "").strip() or None
    e, conf = inferir(r, ed)
    return {
        "nombre": n, "rubro": r, "edad": ed,
        "info_clave": fila.get("info_clave", ""),
        "eneatipo_inferido": e, "confianza": conf,
        "motivo": "Inferido por rubro '%s' y edad %s." % (r or "no informado", ed or "n/d"),
        "speech_whatsapp": SPEECH[e].format(n=n or "sumado", r=r or "tu rubro"),
        "solucion_rapida": solucion(r),
        "requiere_validacion": (conf == "baja") or (not r),
    }

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 agente_ceo_batch.py prospectos.tsv [salida.jsonl] [salida.csv]")
        sys.exit(1)
    src = Path(sys.argv[1])
    out_jsonl = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".jsonl")
    out_csv   = Path(sys.argv[3]) if len(sys.argv) > 3 else src.with_suffix(".csv")
    with src.open(encoding="utf-8") as f:
        filas = [procesar(r) for r in csv.DictReader(f, delimiter="\t")]
    with out_jsonl.open("w", encoding="utf-8") as f:
        for r in filas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print("OK: %d prospectos -> %s y %s" % (len(filas), out_jsonl, out_csv))

if __name__ == "__main__":
    main()
