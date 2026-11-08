import os
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

TITULO_COTIZACION = "SERVICIOS DE PROCURADOR VIRTUAL Y GESTIÓN DE TRÁMITES"

PARTIDAS_TRAMITES = [
    {
        "material_sku": "TRM-SII-01",
        "descripcion": (
            "Investigación y Gestión en SII: obtención de certificados, "
            "inicio de actividades y revisión de situación tributaria."
        ),
        "cantidad": 1,
        "precio_unitario": 196000,
        "total": 196000,
    },
    {
        "material_sku": "TRM-CBR-02",
        "descripcion": (
            "Trámites en Conservador de Bienes Raíces (CBR): inscripción de títulos, "
            "hipotecas, posesiones efectivas y obtención de copias."
        ),
        "cantidad": 1,
        "precio_unitario": 122500,
        "total": 122500,
    },
    {
        "material_sku": "TRM-AJU-03",
        "descripcion": (
            "Gestión en Archivo Judicial: búsqueda de causas, obtención de copias "
            "autorizadas y seguimiento de expedientes."
        ),
        "cantidad": 1,
        "precio_unitario": 98000,
        "total": 98000,
    },
    {
        "material_sku": "TRM-RCV-04",
        "descripcion": (
            "Trámites en Registro Civil: certificados de nacimiento, matrimonio, "
            "defunción y antecedentes."
        ),
        "cantidad": 1,
        "precio_unitario": 73500,
        "total": 73500,
    },
]


def generar_pdf_comercial(nombre_cliente, proyecto, detalle, salida="cotizacion.pdf", titulo=TITULO_COTIZACION):
    print(f"Generando PDF comercial para {nombre_cliente} - Proyecto: {proyecto}...")

    partidas_raw = detalle.get("partidas", [])
    partidas = []

    for p in partidas_raw:
        cant = p.get("cantidad") if p.get("cantidad") is not None else p.get("cantidad_aprobada", 1)
        p_unit = p.get("precio_unitario") if p.get("precio_unitario") is not None else p.get("precio_unitario_real_clp", 0)
        tot = p.get("total") if p.get("total") is not None else (cant * p_unit)

        partidas.append({
            "material_sku": p.get("material_sku", "SKU-000"),
            "descripcion": p.get("descripcion", "Servicio o material"),
            "cantidad": cant,
            "precio_unitario": p_unit,
            "total": tot
        })

    neto = detalle.get("total", sum(item["total"] for item in partidas))
    iva = neto * 0.19
    total = neto + iva
    fecha_actual = datetime.now().strftime("%d-%m-%Y")

    env = Environment(loader=FileSystemLoader('.'))
    try:
        template = env.get_template('plantilla_cotizacion.html')
    except Exception as e:
        print(f"❌ Error: No se encontró plantilla_cotizacion.html. {e}")
        return None

    html_renderizado = template.render(
        titulo=titulo,
        cliente=nombre_cliente,
        proyecto=proyecto,
        fecha=fecha_actual,
        partidas=partidas,
        neto=neto,
        iva=iva,
        total=total
    )

    HTML(string=html_renderizado, base_url='.').write_pdf(salida)
    print(f"✅ PDF generado exitosamente con WeasyPrint: {salida}")
    return salida


if __name__ == "__main__":
    generar_pdf_comercial(
        nombre_cliente="Estudio Jurídico (Cliente de Prueba)",
        proyecto="COT-PROCURADOR-001",
        detalle={"partidas": PARTIDAS_TRAMITES, "total": 490000},
        salida="cotizacion_procurador_virtual.pdf",
    )
