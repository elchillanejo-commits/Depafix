import argparse
import os
import re
import sys
from pathlib import Path

import pdfplumber
from supabase import create_client
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Configuración
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
MARGEN_PCT = 0.35

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMPLATE_DIR = BASE_DIR

COLUMNAS = {
    "sku": ("SKU", "CODIGO", "CÓDIGO", "COD.", "COD", "ITEM", "CÓD"),
    "descripcion": ("DESCRIPCION", "DESCRIPCIÓN", "DESCRIP", "CONCEPTO", "PRODUCTO", "DETALLE", "GLOSA", "PARTIDA"),
    "unidad": ("UNIDAD", "UNID", "U.M", "UM", "MEDIDA"),
    "cantidad": ("CANTIDAD", "CANT.", "CANT", "QTY"),
    "precio": ("PRECIO UNITARIO", "PRECIO UNIT", "P. UNITARIO", "P.UNITARIO", "P. UNIT", "UNITARIO", "PRECIO"),
    "total": ("TOTAL", "SUBTOTAL"),
}
FILAS_RESUMEN = (
    "SUBTOTAL", "SUB-TOTAL", "TOTAL", "NETO", "IVA", "IMPUESTO", "IMPTO",
    "DESCUENTO", "ANTICIPO", "SALDO",
)
NUMERO_RE = re.compile(r"-?\d[\d.,]*")
UNIDAD_RE = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(m2|m²|m3|m³|ml|mt|m|un|und|gl|kg|lt|l|pza|rollo|saco|caja)\b",
    re.IGNORECASE,
)
UNIDAD_SUELTA_RE = re.compile(
    r"\b(m2|m²|m3|m³|ml|mt|m|un|und|gl|kg|lt|l|pza|rollo|saco|caja)\b",
    re.IGNORECASE,
)


def _normalizar(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def _a_numero(texto):
    s = _normalizar(texto).replace("$", "").replace("\xa0", "")
    s = re.sub(
        r"(?<=\d)\s*(m2|m²|m3|m³|ml|mt|un|und|gl|kg|lt|l|pza|rollo|saco|caja)\b",
        "",
        s,
        flags=re.IGNORECASE,
    )
    coincidencias = list(NUMERO_RE.finditer(s))
    if not coincidencias:
        return None
    s = coincidencias[-1].group(0).rstrip(".,")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        partes = s.split(",")
        if len(partes) == 2 and len(partes[1]) in (1, 2):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "." in s:
        partes = s.split(".")
        if len(partes) > 2:
            s = s.replace(".", "")
        elif len(partes) == 2 and len(partes[1]) == 3 and len(partes[0]) <= 3:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _es_resumen(texto):
    t = _normalizar(texto).upper().strip(" :.-")
    return any(
        t == p or t.startswith(p + " ") or t.startswith(p + ":") or t.startswith(p + "(")
        for p in FILAS_RESUMEN
    )


def _detectar_columnas(fila):
    celdas = [_normalizar(c).upper() for c in fila]
    mapa = {}
    for campo, claves in COLUMNAS.items():
        for i, celda in enumerate(celdas):
            if i in mapa.values():
                continue
            if any(clave in celda for clave in claves):
                mapa[campo] = i
                break
    if "descripcion" in mapa and "precio" in mapa:
        return mapa
    return None


def _partida_desde_fila(fila, mapa):
    celdas = [_normalizar(c) for c in fila]

    def celda(campo):
        i = mapa.get(campo)
        return celdas[i] if i is not None and i < len(celdas) else ""

    descripcion = celda("descripcion")
    if not descripcion or _es_resumen(descripcion):
        return None

    precio = _a_numero(celda("precio"))
    if precio is None or precio <= 0:
        return None

    cantidad = _a_numero(celda("cantidad"))
    total = _a_numero(celda("total"))
    if cantidad is None and total and precio:
        cantidad = total / precio
    if cantidad is None or cantidad <= 0:
        return None

    return {
        "material_sku": celda("sku"),
        "descripcion": descripcion,
        "cantidad": cantidad,
        "unidad": celda("unidad") or "un",
        "precio_unitario": precio,
    }


def _partida_desde_linea(texto, desde_tabla=False):
    t = _normalizar(texto)
    if not t or _es_resumen(t):
        return None

    sku = ""
    resto = t
    coincidencia_sku = re.match(r"^([A-Za-z0-9][A-Za-z0-9._/-]{1,})\s+(.+)$", t)
    if coincidencia_sku:
        candidato = coincidencia_sku.group(1)
        parece_sku = (
            (bool(re.search(r"[A-Za-z]", candidato)) and bool(re.search(r"\d", candidato)))
            or bool(re.fullmatch(r"[A-Z][A-Z0-9./-]{2,}", candidato))
            or ("-" in candidato and len(candidato) >= 5)
        )
        if parece_sku:
            sku = candidato
            resto = coincidencia_sku.group(2)

    if not desde_tabla:
        primer_token = t.split()[0] if t.split() else ""
        parece_sku = (
            len(primer_token) >= 4
            and bool(re.search(r"[A-Za-z]", primer_token))
            and bool(re.search(r"\d", primer_token))
        )
        if "$" not in t and not parece_sku:
            return None

    tokens = []
    for m in NUMERO_RE.finditer(resto):
        valor = _a_numero(m.group(0))
        if valor is None:
            continue
        monetario = bool(re.search(r"\$\s*$", resto[: m.start()]))
        tokens.append((valor, m.start(), m.end(), monetario))

    if "GLOBAL" in t.upper():
        monetarios_global = [token for token in tokens if token[3]]
        if not tokens:
            return None
        precio = (monetarios_global[-1] if monetarios_global else tokens[-1])[0]
        if precio <= 0:
            return None
        descripcion = re.split(r"\bGLOBAL\b", t, maxsplit=1, flags=re.IGNORECASE)[0]
        descripcion = _normalizar(descripcion).strip(" -:|")
        if len(descripcion) < 3:
            return None
        return {
            "material_sku": sku,
            "descripcion": descripcion,
            "cantidad": 1.0,
            "unidad": "global",
            "precio_unitario": precio,
        }

    if len(tokens) < 2:
        return None

    monetarios = [i for i, token in enumerate(tokens) if token[3]]
    if len(monetarios) >= 2:
        indice_precio, indice_total = monetarios[-2], monetarios[-1]
    elif len(monetarios) == 1:
        indice_precio, indice_total = monetarios[-1], None
    else:
        indice_precio, indice_total = len(tokens) - 2, len(tokens) - 1

    precio = tokens[indice_precio][0]
    total = tokens[indice_total][0] if indice_total is not None else None

    indice_cantidad = None
    for i in range(indice_precio - 1, -1, -1):
        if i == indice_total:
            continue
        indice_cantidad = i
        break
    if indice_cantidad is None:
        return None

    cantidad = tokens[indice_cantidad][0]
    if cantidad <= 0 or precio <= 0:
        return None

    if total is not None and abs(total - cantidad * precio) > max(1.0, abs(total) * 0.02):
        if len(tokens) >= 2:
            precio = tokens[-1][0]
            cantidad = tokens[-2][0]
            total = None
        else:
            return None

    descripcion = _normalizar(resto[: tokens[indice_cantidad][1]]).strip(" -:|\t")
    descripcion = re.sub(r"^(?:\d+\s+){1,3}", "", descripcion).strip()
    if len(descripcion) < 3:
        return None

    unidad = "un"
    coincidencia_unidad = UNIDAD_RE.search(resto)
    if coincidencia_unidad:
        unidad = coincidencia_unidad.group(2).replace(" ", "").lower()
    else:
        coincidencia_unidad = UNIDAD_SUELTA_RE.search(descripcion)
        if coincidencia_unidad:
            unidad = coincidencia_unidad.group(1).replace(" ", "").lower()
    if unidad in ("m", "m2", "m²"):
        unidad = "m2"

    return {
        "material_sku": sku,
        "descripcion": descripcion,
        "cantidad": cantidad,
        "unidad": unidad,
        "precio_unitario": precio,
    }


def _agregar_partida(partidas, vistos, claves_tabla, partida, de_tabla):
    clave = (
        partida["descripcion"].upper(),
        round(partida["cantidad"], 4),
        round(partida["precio_unitario"], 2),
    )
    clave_numerica = (round(partida["cantidad"], 4), round(partida["precio_unitario"], 2))
    if clave in vistos or (clave_numerica in claves_tabla and not de_tabla):
        return
    vistos.add(clave)
    if de_tabla:
        claves_tabla.add(clave_numerica)
    partidas.append(partida)


def procesar_pdf(ruta_pdf, proyecto, proveedor, sku_prefix, fecha_requerida):
    ruta = Path(ruta_pdf)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el PDF: {ruta}")

    partidas = []
    vistos = set()
    claves_tabla = set()

    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables() or []:
                if not tabla:
                    continue
                mapa = _detectar_columnas(tabla[0])
                if not mapa:
                    continue
                for fila in tabla:
                    partida = _partida_desde_fila(fila, mapa)
                    if partida is None:
                        partida = _partida_desde_linea(
                            " ".join(str(c or "") for c in fila),
                            desde_tabla=True,
                        )
                    if partida:
                        _agregar_partida(partidas, vistos, claves_tabla, partida, de_tabla=True)

            texto = pagina.extract_text() or ""
            for linea in texto.splitlines():
                partida = _partida_desde_linea(linea)
                if partida:
                    _agregar_partida(partidas, vistos, claves_tabla, partida, de_tabla=False)

    if not partidas:
        raise ValueError(
            "No se encontraron partidas en el PDF. Se esperaba una tabla con "
            "columnas de descripción, cantidad y precio unitario."
        )

    for i, partida in enumerate(partidas, start=1):
        if not partida.get("material_sku"):
            partida["material_sku"] = f"{sku_prefix}-{i:03d}"

    print(f"✅ {len(partidas)} partidas extraídas del PDF")
    return partidas

def _aplicar_margen(partidas):
    for p in partidas:
        precio_real = float(p["precio_unitario"])
        precio_cliente = round(precio_real * (1 + MARGEN_PCT), 2)
        p["precio_unitario_real"] = precio_real
        p["precio_unitario_cliente"] = precio_cliente
        p["precio_unitario"] = precio_cliente
        p["total"] = round(float(p["cantidad"]) * precio_cliente, 2)
    return partidas


def guardar_materiales(cliente, proyecto, partidas, proveedor, fecha_requerida):
    registros = []
    vistos = set()
    for i, p in enumerate(partidas, start=1):
        sku = (p.get("material_sku") or "").strip() or f"AUTO-{i:03d}"
        clave = (sku, p["descripcion"].strip())
        if clave in vistos:
            continue
        vistos.add(clave)

        cantidad = float(p["cantidad"])
        precio_real = float(p.get("precio_unitario_real", p["precio_unitario"]))
        precio_cliente = float(
            p.get("precio_unitario_cliente", round(precio_real * (1 + MARGEN_PCT), 2))
        )

        registros.append({
            "proyecto_codigo": proyecto,
            "material_sku": sku,
            "descripcion": p["descripcion"],
            "cantidad_aprobada": cantidad,
            "precio_unitario_real_clp": round(precio_real, 2),
            "margen_aplicado_pct": round(MARGEN_PCT * 100, 2),
            "precio_unitario_cliente_clp": precio_cliente,
            "estado_compra": "pendiente",
            "fecha_requerida": fecha_requerida,
            "notas": f"Cotizacion proveedor {proveedor}",
        })

    if not registros:
        print("⚠️ No hay partidas para guardar.")
        return 0

    cliente.table("proyecto_materiales").delete().eq("proyecto_codigo", proyecto).execute()

    respuesta = (
        cliente.table("proyecto_materiales")
        .insert(registros)
        .execute()
    )
    filas = respuesta.data or []
    print(f"✅ Materiales guardados en '{proyecto}': {len(filas)} partidas (margen {MARGEN_PCT * 100:.0f}%)")
    return len(filas)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", required=True)
    parser.add_argument("--proyecto", required=True)
    parser.add_argument("--proveedor", required=True)
    parser.add_argument("--sku-prefix", required=True)
    parser.add_argument("--fecha-requerida", required=True)
    args = parser.parse_args()

    print(f"🔍 Procesando PDF: {args.archivo}")

    partidas = procesar_pdf(args.archivo, args.proyecto, args.proveedor, args.sku_prefix, args.fecha_requerida)
    print(f"💰 Aplicando margen del {MARGEN_PCT * 100:.0f}%...")
    _aplicar_margen(partidas)

    costo_real = sum(p["cantidad"] * p["precio_unitario_real"] for p in partidas)
    total_neto = sum(p["total"] for p in partidas)
    iva = round(total_neto * 0.19, 2)
    total = round(total_neto + iva, 2)
    print(f"Costo real proveedor: ${costo_real:,.0f}")
    print(f"Venta neta (+{MARGEN_PCT * 100:.0f}%): ${total_neto:,.0f} | IVA: ${iva:,.0f} | Total: ${total:,.0f}")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env")
    cliente = create_client(SUPABASE_URL, SUPABASE_KEY)
    guardar_materiales(cliente, args.proyecto, partidas, args.proveedor, args.fecha_requerida)

    # Renderizar plantilla HTML con Jinja2
    print("📄 Generando presupuesto HTML...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("plantilla_cotizacion.html")

    html = template.render(
        cliente=args.proveedor,
        proyecto=args.proyecto,
        fecha=args.fecha_requerida,
        partidas=partidas,
        neto=total_neto,
        iva=iva,
        total=total
    )

    archivo_salida = os.path.join(OUTPUT_DIR, f"presupuesto_{args.proyecto}.html")
    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Proceso finalizado con éxito. Presupuesto guardado en: {archivo_salida}")

if __name__ == "__main__":
    main()
