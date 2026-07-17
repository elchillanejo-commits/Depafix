#!/usr/bin/env python3
"""
Generador de reporte ejecutivo en PDF para DepaFix.
Uso: python3 generar_reporte.py [--tipo mensual|semanal]
"""
import os
import sys
import argparse
from datetime import datetime, timedelta
import psycopg2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# Configuración de BD
DB_CONFIG = {
    "host": "localhost",
    "dbname": "depafix",
    "user": "depafix",
    "password": os.getenv("PGPASSWORD")  # sin fallback: credencial hardcodeada removida (auditoria 2026-07-16, repo publico)
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def fmt_clp(valor):
    return "${:,.0f}".format(valor).replace(",", ".")

def consultar_metricas(tipo="mensual"):
    """Consulta las métricas de negocio."""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    
    # Filtro de fecha según tipo
    if tipo == "mensual":
        fecha_inicio = now.replace(day=1).date()
    else:  # semanal
        fecha_inicio = (now - timedelta(days=7)).date()
    
    # Total presupuestos
    cur.execute("SELECT COUNT(*) FROM obras.presupuestos")
    total_presupuestos = cur.fetchone()[0]
    
    # Presupuestos del periodo
    cur.execute("""
        SELECT COUNT(*) FROM obras.presupuestos 
        WHERE fecha::date >= %s
    """, (fecha_inicio,))
    presupuestos_periodo = cur.fetchone()[0]
    
    # Facturación del periodo (estado aprobado/pagado)
    cur.execute("""
        SELECT COALESCE(SUM(total), 0) FROM obras.presupuestos 
        WHERE estado IN ('aprobado', 'pagado', 'completado')
        AND fecha::date >= %s
    """, (fecha_inicio,))
    facturacion = cur.fetchone()[0]
    
    # Top 5 clientes
    cur.execute("""
        SELECT pc.cliente, COALESCE(SUM(p.total), 0) AS total
        FROM obras.presupuestos_cliente pc
        JOIN obras.presupuestos p ON pc.presupuesto_id = p.id
        GROUP BY pc.cliente
        ORDER BY total DESC
        LIMIT 5
    """)
    top_clientes = cur.fetchall()
    
    # Distribución por comuna (si existe la tabla)
    try:
        cur.execute("""
            SELECT c.comuna, COUNT(p.id)
            FROM obras.presupuestos p
            JOIN obras.presupuestos_cliente pc ON p.id = pc.presupuesto_id
            JOIN obras.clientes c ON pc.cliente = c.id
            WHERE c.comuna IS NOT NULL
            GROUP BY c.comuna
            ORDER BY 2 DESC
            LIMIT 5
        """)
        comunas = cur.fetchall()
    except:
        comunas = [("Sin datos", 0)]
    
    # Alertas críticas
    try:
        cur.execute("""
            SELECT tipo, mensaje FROM siegfried.alertas 
            WHERE estado = 'CRITICO' 
            ORDER BY id DESC LIMIT 5
        """)
        alertas = cur.fetchall()
    except:
        alertas = []
    
    cur.close()
    conn.close()
    
    return {
        "total_presupuestos": total_presupuestos,
        "presupuestos_periodo": presupuestos_periodo,
        "facturacion": facturacion,
        "top_clientes": top_clientes,
        "comunas": comunas,
        "alertas": alertas,
        "periodo": tipo,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": now.date()
    }

def grafico_barras(datos, titulo, xlabel, ylabel):
    """Genera un gráfico de barras y devuelve un objeto Image de reportlab."""
    if not datos:
        return None
    fig, ax = plt.subplots(figsize=(6, 3.5))
    labels = [d[0] for d in datos]
    values = [float(d[1]) for d in datos]
    ax.bar(labels, values, color='#2ea043')
    ax.set_title(titulo)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    buf.seek(0)
    return Image(buf, width=400, height=200)

def generar_pdf(metricas, tipo="mensual"):
    """Genera el PDF del reporte."""
    fecha_str = datetime.now().strftime("%Y%m%d")
    pdf_path = os.path.expanduser(f"~/tmp/reporte_ejecutivo_{fecha_str}.pdf")
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []
    
    # Estilos personalizados
    titulo_style = ParagraphStyle('Titulo', parent=styles['Title'], alignment=TA_CENTER,
                                   fontSize=24, textColor=colors.HexColor('#0a1e2e'), spaceAfter=6)
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'], alignment=TA_CENTER,
                                      fontSize=12, textColor=colors.HexColor('#6b8a9e'), spaceAfter=16)
    seccion_style = ParagraphStyle('Seccion', parent=styles['Heading3'], fontSize=14,
                                    textColor=colors.HexColor('#0a1e2e'), spaceAfter=8, spaceBefore=12)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10,
                                   textColor=colors.HexColor('#2d3748'), leading=14)
    
    # Logo (opcional)
    logo_path = os.path.expanduser("~/Proyectos/DepaFix/core/static/logo.png")
    if os.path.exists(logo_path):
        # No implementamos imagen por simplicidad, pero se podría agregar.
        pass
    
    # Header
    story.append(Paragraph("DEPAFIX", titulo_style))
    story.append(Paragraph("Reporte Ejecutivo de Negocio", subtitulo_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("<hr color='#0a1e2e' size='2' width='100%' />", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Información del reporte
    periodo_texto = "Mensual" if tipo == "mensual" else "Semanal"
    story.append(Paragraph(f"Reporte {periodo_texto}", titulo_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Periodo: {metricas['fecha_inicio']} a {metricas['fecha_fin']}", normal_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Resumen de métricas
    story.append(Paragraph("Resumen de Métricas", seccion_style))
    resumen_data = [
        ["Métrica", "Valor"],
        ["Total presupuestos", str(metricas['total_presupuestos'])],
        [f"Presupuestos {periodo_texto.lower()}", str(metricas['presupuestos_periodo'])],
        [f"Facturación {periodo_texto.lower()}", fmt_clp(metricas['facturacion'])]
    ]
    tabla_res = Table(resumen_data, colWidths=[8*cm, 6*cm])
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
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f7fafc')]),
    ]))
    story.append(tabla_res)
    story.append(Spacer(1, 0.5*cm))
    
    # Top 5 clientes
    if metricas['top_clientes']:
        story.append(Paragraph("Top 5 Clientes", seccion_style))
        clientes_data = [["Cliente", "Total Facturado"]]
        for nombre, total in metricas['top_clientes']:
            clientes_data.append([nombre or "Sin nombre", fmt_clp(total)])
        tabla_clientes = Table(clientes_data, colWidths=[7*cm, 7*cm])
        tabla_clientes.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0a1e2e')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        story.append(tabla_clientes)
        story.append(Spacer(1, 0.5*cm))
    
    # Gráfico de comunas (si hay datos)
    if metricas['comunas'] and metricas['comunas'][0][0] != "Sin datos":
        story.append(Paragraph("Distribución por Comuna", seccion_style))
        img = grafico_barras(metricas['comunas'], "Obras por Comuna", "Comuna", "Cantidad")
        if img:
            story.append(img)
        story.append(Spacer(1, 0.5*cm))
    
    # Alertas críticas
    if metricas['alertas']:
        story.append(Paragraph("Alertas Críticas", seccion_style))
        for tipo, mensaje in metricas['alertas']:
            story.append(Paragraph(f"• <b>{tipo}</b>: {mensaje}", normal_style))
    else:
        story.append(Paragraph("Sin alertas críticas.", normal_style))
    
    # Pie de página
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("<hr color='#e2e8f0' size='1' width='100%' />", styles['Normal']))
    pie = f"""
    <font size='8' color='#a0aec0'>
    Reporte generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}.<br/>
    DepaFix - Gestión de Mantención y Proyectos
    </font>
    """
    story.append(Paragraph(pie, styles['Normal']))
    
    doc.build(story)
    return pdf_path

def main():
    parser = argparse.ArgumentParser(description="Generar reporte ejecutivo")
    parser.add_argument("--tipo", choices=["mensual", "semanal"], default="mensual",
                        help="Tipo de reporte (mensual o semanal)")
    args = parser.parse_args()
    
    metricas = consultar_metricas(args.tipo)
    pdf_path = generar_pdf(metricas, args.tipo)
    print(f"✅ Reporte generado: {pdf_path}")

if __name__ == "__main__":
    main()
