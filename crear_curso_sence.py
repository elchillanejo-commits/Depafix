#!/usr/bin/env python3
"""crear_curso_sence.py — Crea un curso en `cursos_sence` desde un PDF.

Extrae los campos típicos de una ficha de curso SENCE (código, horas,
participantes, competencia, aprendizajes, contenidos, relatores, costos)
con pdfplumber + regex, e inserta (upsert por `codigo_sence`) en Supabase.

También funciona con facturas SENCE (ej. "Servicios de capacitación ... Código
Sence: 1238088484 ... Horas: 20 ... Participantes: 19"): en ese caso los campos
que no aparecen quedan vacíos y `estado` queda en 'borrador'.

Uso:
    python3 crear_curso_sence.py --archivo 62RAI_ExceleBasico.pdf
    python3 crear_curso_sence.py --archivo curso.pdf --estado enviado_sence
    python3 crear_curso_sence.py --archivo curso.pdf --dry-run   # solo extrae, no inserta
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

ESTADOS_VALIDOS = ("borrador", "enviado_sence", "aprobado", "ejecutando", "liquidado")

# Secciones reconocidas; se usan para cortar los bloques (aprendizajes, contenidos...).
CORTES = [
    r"competenc",
    r"aprendizaje",
    r"contenido",
    r"relator",
    r"costo",
    r"modalidad",
    r"participante",
    r"c[oó]digo",
    r"horas",
    r"nombre",
    r"fecha",
]


def crear_supabase():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SystemExit("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el .env")
    from supabase import create_client

    return create_client(url, key)


def extraer_texto_pdf(ruta: Path) -> str:
    with pdfplumber.open(str(ruta)) as pdf:
        lineas = []
        for pagina in pdf.pages:
            lineas.append(pagina.extract_text() or "")
        return "\n".join(lineas)


def buscar(patrones, texto):
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def parsear_clp(valor):
    if not valor:
        return 0.0
    digitos = re.sub(r"[^\d]", "", str(valor))
    return float(digitos) if digitos else 0.0


def parsear_int(valor):
    if not valor:
        return None
    digitos = re.sub(r"[^\d]", "", str(valor))
    return int(digitos) if digitos else None


def extraer_bloque(texto, inicio_patrones):
    """Devuelve el texto entre la cabecera indicada y la siguiente cabecera."""
    for patron in inicio_patrones:
        m = re.search(patron, texto, re.IGNORECASE)
        if not m:
            continue
        inicio = m.end()
        fin = len(texto)
        for corte in CORTES:
            fm = re.search(corte, texto[inicio:], re.IGNORECASE)
            if fm and inicio + fm.start() < fin:
                fin = inicio + fm.start()
        return texto[inicio:fin].strip(" \n:-")
    return None


def extraer_items(bloque, max_items=50):
    if not bloque:
        return []
    items = re.split(r"[\n•\-–*;]|(?:\n\s*\d+\.\s)", bloque)
    limpios = [i.strip(" \t-") for i in items if len(i.strip()) >= 3]
    return limpios[:max_items]


def _normalizar_modalidad(valor):
    if not valor:
        return None
    valor = re.sub(r"(?i)^(?:\d+\.?\s*-?\s*)?(?:modalidad\s+de\s+capacitaci[oó]n\s*[:\-]?\s*)", "", valor.strip())
    valor = re.sub(r"\s+", " ", valor).strip(" :-")
    valor = valor.replace("Sincronico", "Sincrónico").replace("sincronico", "sincrónico")
    return valor or None


def _limpiar_competencia(valor):
    if not valor:
        return None
    valor = re.sub(r"\s+", " ", valor).strip(" :-")
    valor = re.sub(r"(?i)^6\.\s*-\s*competencia\s+a\s+desarrollar\s*:\s*", "", valor)
    return valor or None


EXCLUIR_NOMBRE = {
    "experiencia", "formaci", "sobre", "nombre", "rut", "formación", "post", "grado",
    "magister", "doctorado", "curso", "cursos", "especialización", "diplomados",
    "diplomado", "universitaria", "técnico", "postgrado",
}


def _extraer_nombre_columna(lineas, patron_columna):
    partes = []
    for line in lineas:
        if not line.strip():
            continue
        m = re.search(patron_columna, line)
        if m:
            partes.append(m.group(1).strip())
    return " ".join(partes).strip() or None


def _es_ruido_nombre(valor):
    if not valor:
        return True
    bajo = valor.lower().strip()
    return any(palabra in bajo for palabra in EXCLUIR_NOMBRE) or bajo in ("de", "del", "la", "el", "en", "y")


def _primera_columna(linea):
    if not linea.strip():
        return ""
    espacios = re.split(r"\s{2,}", linea.strip())
    if len(espacios) > 1:
        return espacios[0].strip()
    return linea.strip().split()[0] if linea.strip().split() else ""


def extraer_relatores(texto):
    texto = texto or ""
    m_full = re.search(r"(?i)full\s+name\s*:\s*([^\n]{3,100})", texto)
    if m_full:
        return [{"nombre": m_full.group(1).strip(), "rut": None}]
    relatores = []
    lineas_totales = texto.splitlines()
    for idx, line in enumerate(lineas_totales):
        m_run = re.match(r"^\s*(\d{7,9})\s+años", line)
        if not m_run:
            continue
        run = m_run.group(1)
        bloque_prev = []
        bloque_post = []
        for k in range(idx - 3, idx):
            if k < 0 or k >= len(lineas_totales):
                continue
            primera = _primera_columna(lineas_totales[k])
            if primera and primera.isupper() and len(primera) >= 3 and not _es_ruido_nombre(primera):
                for b in primera.split():
                    b = b.strip(" _.,;-")
                    if b and b.isupper() and len(b) >= 3 and b.lower() not in EXCLUIR_NOMBRE and b not in bloque_prev:
                        bloque_prev.append(b)
        for k in range(idx + 1, idx + 5):
            if k < 0 or k >= len(lineas_totales):
                continue
            primera = _primera_columna(lineas_totales[k])
            if primera and primera.isupper() and len(primera) >= 3 and not _es_ruido_nombre(primera):
                for b in primera.split():
                    b = b.strip(" _.,;-")
                    if b and b.isupper() and len(b) >= 3 and b.lower() not in EXCLUIR_NOMBRE and b not in bloque_post:
                        bloque_post.append(b)
        nombre = None
        if len(bloque_prev) >= 1 and bloque_post:
            nombre = " ".join(p.title() for p in bloque_prev + bloque_post)
        if nombre:
            nombre = re.sub(r"\s+", " ", nombre).strip()
            if nombre.isupper():
                nombre = nombre.title()
            nombre = nombre[0].upper() + nombre[1:] if nombre else nombre
            if not _es_ruido_nombre(nombre) and nombre not in [x["nombre"] for x in relatores]:
                relatores.append({"nombre": nombre, "rut": None})
    if not relatores:
        patron_alt = re.search(
            r"(?s)([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]+){1,3})\s*\n\s*\d{7,9}\s+años",
            texto,
        )
        if patron_alt:
            nombre = patron_alt.group(1).strip()
            nombre = nombre.title() if nombre.isupper() else nombre
            if not _es_ruido_nombre(nombre):
                relatores.append({"nombre": nombre, "rut": None})
    return relatores


def extraer_curso(texto: str, codigo_manual=None) -> dict:
    # Código SENCE (ej: 1238088484) o Numero Solicitud: 1915171
    codigo = codigo_manual or buscar(
        [
            r"c[oó]digo\s*(?:sence|del\s+curso|curso)?\s*[:#]?\s*(\d{6,10})",
            r"c[oó]d\.?\s*sence\s*[:#]?\s*(\d{6,10})",
            r"n[uú]mero\s+solicitud\s*[:#]?\s*(\d{6,10})",
        ],
        texto,
    )
    if codigo:
        codigo = str(codigo).strip()

    # Nombre del curso. Factura: la descripción del servicio es una línea
    # EXACTA "Servicios de capacitación" y el curso va en la línea siguiente
    # (p. ej. "Herramientas Digitales en Entornos Laborales" + posible
    # línea "(Pre-Contrato)"). Se usa patrón anclado multi-línea para no
    # confundir con "Giro: SERVICIOS DE CAPACITACIÓN".
    nombre = None
    m = re.search(
        r"(?m)^\s*servicios?\s+de\s+capacitaci[oó]n\b[^\n]*$\n"
        r"([^\n]{5,200}(?:\n\s*\([^\n]{1,80}\))?)",
        texto,
        re.IGNORECASE,
    )
    if m:
        nombre = re.sub(r"\s*\n\s*", " ", m.group(1)).strip()
    if not nombre:
        nombre = buscar(
            [
                r"(?:programa\s+del\s+curso|nombre\s+del\s+curso|nombre)\s*[:\-]?\s*([^\n]{5,160})",
                r"curso\s*[:\-]?\s*([^\n]{5,160})",
            ],
            texto,
        )

    modalidad = _normalizar_modalidad(
        buscar(
            [
                r"modalidad\s+de\s+capacitaci[oó]n\s*[:\-]?\s*([^\n]{2,80})",
                r"modalidad\s*[:\-]?\s*([A-Za-zÁÉÍÓÚáéíóú][^\n]{0,80})",
            ],
            texto,
        )
    )

    horas = parsear_int(
        buscar(
            [
                r"total\s+horas\s+cronol[oó]gicas\s+del\s+curso\s*[:\-]?\s*(\d{1,3})",
                r"horas\s*(?:cronol[oó]gicas|cronol[oó]gicas)?\s*[:\-]?\s*(\d{1,4})",
                r"n[°ºo]?\s*horas\s*[:\-]?\s*(\d{1,4})",
                r"duraci[oó]n\s*[:\-]?\s*(\d{1,4})\s*h",
            ],
            texto,
        )
    )

    participantes = parsear_int(
        buscar(
            [
                r"n[úu]mero\s+de\s+participantes\s*[:\-]?\s*(\d{1,4})",
                r"participantes?\s*[:\-]?\s*(\d{1,4})",
                r"n[°ºo]\s*(?:de\s*)?participantes?\s*[:\-]?\s*(\d{1,4})",
            ],
            texto,
        )
    )

    competencia = _limpiar_competencia(
        buscar(
            [
                r"competencia\s+a\s+desarrollar\s*[:\-]?\s*([^\n]{5,400})",
                r"competenc(?:ia|ias)\s*laboral\s*[:\-]?\s*([^\n]{5,200})",
                r"competencia\s*[:\-]?\s*([^\n]{5,200})",
            ],
            texto,
        )
    )

    aprendizajes = extraer_items(
        extraer_bloque(texto, [r"aprendizajes\s+esperados?\s*[:\-]?", r"aprendizajes\s*[:\-]?"])
    )

    contenidos = extraer_items(
        extraer_bloque(texto, [r"contenidos?\s*(?:del\s+curso)?\s*[:\-]?"])
    )

    relatores = extraer_relatores(texto)

    def costo(concepto):
        return parsear_clp(
            buscar(
                [
                    rf"costos?\s*{concepto}\s*[:\-]?\s*([\d\.\s]+)",
                    rf"(?:costo|valor)\s*(?:del\s+)?{concepto}\s*[:\-$]?\s*\$?\s*([\d\.]+)",
                    rf"{concepto}\s*[:\-$]?\s*\$?\s*([\d\.]+)",
                ],
                texto,
            )
        )

    costo_facilitador = costo(r"(?:facilitador(?:\s*/\s*instructores?\s*/\s*relatores)?|instructores?\s*/\s*relatores)")
    costo_infraestructura = costo(r"infraestructura")
    costo_materiales = costo(r"materiales(?:\s+y\s+equipos)?")
    costo_utilidades = costo(r"utilidades")
    total = buscar([r"la\s+suma\s+de\s+todos\s+los\s+[íi]tems\s+activos\s*[:\-]?\s*([\d\.\s]+)"], texto)
    total = parsear_clp(total) if total else 0.0
    if total == 0.0:
        total = costo_facilitador + costo_infraestructura + costo_materiales + costo_utilidades

    return {
        "codigo_sence": codigo,
        "nombre_curso": nombre.replace("\n", " ").strip() if nombre else None,
        "modalidad": modalidad,
        "horas_cronologicas": horas,
        "numero_participantes": participantes,
        "competencia": competencia,
        "aprendizajes_esperados": aprendizajes,
        "contenidos": contenidos,
        "relatores": relatores,
        "costo_facilitador": round(costo_facilitador, 2),
        "costo_infraestructura": round(costo_infraestructura, 2),
        "costo_materiales": round(costo_materiales, 2),
        "costo_utilidades": round(costo_utilidades, 2),
        "total_curso": round(total, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Crea/actualiza un curso en cursos_sence desde un PDF.")
    parser.add_argument("--archivo", required=True, help="Ruta del PDF (ej: ExcelBasico.pdf)")
    parser.add_argument("--codigo_sence", default=None, help="Código SENCE manual si el PDF no lo trae (ej: 1915171)")
    parser.add_argument("--estado", default="borrador", choices=ESTADOS_VALIDOS)
    parser.add_argument("--dry-run", action="store_true", help="Solo extrae y muestra; no inserta.")
    args = parser.parse_args()

    ruta = Path(args.archivo).expanduser().resolve()
    if not ruta.exists():
        raise SystemExit(f"No existe el archivo: {ruta}")
    if ruta.suffix.lower() != ".pdf":
        raise SystemExit("El archivo debe ser un PDF")

    texto = extraer_texto_pdf(ruta)
    curso = extraer_curso(texto, codigo_manual=args.codigo_sence)
    curso["estado"] = args.estado

    print(json.dumps(curso, ensure_ascii=False, indent=2))

    faltantes = [k for k in ("codigo_sence", "nombre_curso") if not curso.get(k)]
    if faltantes:
        print(f"\n⚠️ Faltan campos obligatorios: {', '.join(faltantes)}", file=sys.stderr)
        raise SystemExit(1)

    if args.dry_run:
        print("\n(dry-run: no se insertó nada en Supabase)")
        return

    cliente = crear_supabase()
    respuesta = cliente.table("cursos_sence").upsert(
        curso, on_conflict="codigo_sence"
    ).execute()
    filas = respuesta.data or []
    print(f"\n✅ Curso {curso['codigo_sence']} guardado en cursos_sence ({len(filas)} fila(s)).")


if __name__ == "__main__":
    main()
