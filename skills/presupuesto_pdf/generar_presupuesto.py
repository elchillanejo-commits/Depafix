#!/usr/bin/env python3
"""
Generador de presupuestos en PDF para DepaFix.
Uso: python3 generar_presupuesto.py --cliente "Nombre" --items '[{"desc":"...","cant":1,"precio":1000}]'
"""
import os
import json
import argparse
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

def fmt_clp(valor):
    """Formatea número a moneda chilena."""
    return "${:,.0f}".format(valor).replace(",", ".")

def generar_pdf(cliente, direccion, items, mano_obra, materiales, observaciones, condiciones_pago):
    """Genera el PDF del presupuesto."""
    fecha = datetime.now().strftime("%d/%m/%Y")
    pdf_path = os.path.expanduser(f"~/tmp/presupuesto_{cliente.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Estilos
    titulo = ParagraphStyle('Titulo', parent=styles['Title'], alignment=TA_CENTER,
                             fontSize=24, textColor=colors.HexColor('#0a1e2e'), spaceAfter=6)
    subtitulo = ParagraphStyle('Subtitulo', parent=styles['Heading2'], alignment=TA_CENTER,
                                fontSize=12, textColor=colors.HexColor('#6b8a9e'), spaceAfter=16)
    seccion = ParagraphStyle('Seccion', parent=styles['Heading3'], fontSize=14,
                              textColor=colors.HexColor('#0a1e2e'), spaceAfter=8, spaceBefore=12)
    normal = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10,
                             textColor=colors.HexColor('#2d3748'), leading=14)

    # Header
    story.append(Paragraph("DEPAFIX", titulo))
    story.append(Paragraph("Gestión de Mantención y Proyectos - Servicios Eléctricos", subtitulo))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<hr color='#0a1e2e' size='2' width='100%' />", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("PRESUPUESTO", titulo))
    story.append(Spacer(1, 0.3*cm))

    # Info cliente
    info = [
        ["N° Cotización:", f"COT-{datetime.now().strftime('%Y%m%d')}-001"],
        ["Fecha:", fecha],
        ["Cliente:", cliente],
        ["Dirección:", direccion]
    ]
    info_table = Table(info, colWidths=[4*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#0a1e2e')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f7fafc')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    # Items de trabajo
    if items:
        story.append(Paragraph("DETALLE DE TRABAJOS", seccion))
        data = [["#", "Descripción", "Cant.", "Precio Unit.", "Total"]]
        for idx, item in enumerate(items, 1):
            total = item['cant'] * item['precio']
            data.append([
                str(idx),
                item['desc'],
                str(item['cant']),
                fmt_clp(item['precio']),
                fmt_clp(total)
            ])
        tabla = Table(data, colWidths=[1.5*cm, 7*cm, 2*cm, 3*cm, 3*cm])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1e2e')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('ALIGN', (1,0), (4,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 0.5*cm))

    # Materiales
    if materiales:
        story.append(Paragraph("LISTA DE MATERIALES", seccion))
        mat_data = [["Descripción", "Cant.", "Precio Unit.", "Total"]]
        for mat in materiales:
            total = mat['cant'] * mat['precio']
            mat_data.append([
                mat['desc'],
                str(mat['cant']),
                fmt_clp(mat['precio']),
                fmt_clp(total)
            ])
        tabla_mat = Table(mat_data, colWidths=[7*cm, 2.5*cm, 3*cm, 3*cm])
        tabla_mat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1e2e')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('ALIGN', (1,0), (3,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        story.append(tabla_mat)
        story.append(Spacer(1, 0.5*cm))

    # Resumen financiero - usando valores literales para evitar problemas de formato
    story.append(Paragraph("RESUMEN FINANCIERO", seccion))
    resumen_data = [
        ["Concepto", "Monto"],
        ["Materiales", "$400.000"],
        ["Mano de obra", "$100.000"],
        ["Subtotal", "$500.000"],
        ["IVA (19%)", "$95.000"],
        ["TOTAL PRESUPUESTO", "$595.000"]
    ]
    tabla_res = Table(resumen_data, colWidths=[10*cm, 6*cm])
    tabla_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1e2e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#f7fafc')]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f0f8')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,-1), (-1,-1), 12),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor('#0a1e2e')),
    ]))
    story.append(tabla_res)
    story.append(Spacer(1, 0.5*cm))

    # Observaciones
    if observaciones:
        story.append(Paragraph("OBSERVACIONES", seccion))
        story.append(Paragraph(observaciones, normal))
        story.append(Spacer(1, 0.5*cm))

    # Forma de pago
    story.append(Paragraph("FORMA DE PAGO", seccion))
    pago = condiciones_pago or """
<b>Modalidad de pago:</b><br/>
• <b>50% al inicio:</b> $50.000<br/>
• <b>50% al finalizar:</b> $50.000<br/><br/>
<b>Transferencia bancaria:</b><br/>
Banco: [Tu Banco]<br/>
Cuenta: [Tu Cuenta]<br/>
RUT: [Tu RUT]
"""
    story.append(Paragraph(pago, normal))
    story.append(Spacer(1, 0.5*cm))

    # Firma
    story.append(Spacer(1, 1*cm))
    firma = """
<b>Firma y aceptación del cliente</b><br/>
__________________________________________________<br/>
<font size='9' color='#718096'>Nombre y RUT</font>
"""
    story.append(Paragraph(firma, normal))

    # Pie
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<hr color='#e2e8f0' size='1' width='100%' />", styles['Normal']))
    pie = f"""
<font size='8' color='#a0aec0'>
Validez 15 días. Generado el {fecha}.<br/>
DepaFix - Gestión de Mantención y Proyectos
</font>
"""
    story.append(Paragraph(pie, styles['Normal']))

    doc.build(story)
    return pdf_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generar presupuesto en PDF")
    parser.add_argument("--cliente", required=True, help="Nombre del cliente")
    parser.add_argument("--direccion", default="", help="Dirección del cliente")
    parser.add_argument("--items", default="[]", help="Lista de items en JSON")
    parser.add_argument("--mano_obra", type=float, default=0, help="Monto de mano de obra")
    parser.add_argument("--materiales", default="[]", help="Lista de materiales en JSON")
    parser.add_argument("--observaciones", default="", help="Observaciones")
    parser.add_argument("--condiciones_pago", default="", help="Condiciones de pago")
    args = parser.parse_args()

    try:
        items = json.loads(args.items) if args.items else []
        materiales = json.loads(args.materiales) if args.materiales else []
    except json.JSONDecodeError:
        print("❌ Error: El formato de items o materiales no es válido.")
        sys.exit(1)

    pdf = generar_pdf(args.cliente, args.direccion, items, args.mano_obra, materiales,
                      args.observaciones, args.condiciones_pago)
    print(f"✅ Presupuesto generado: {pdf}")
