#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generador de PDF para el Motor de Cotización DepaFix."""

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, Union

from xhtml2pdf import pisa


def _clp(valor: Any) -> str:
    try:
        return "$" + f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def _pct(valor: Any) -> str:
    try:
        return f"{float(valor):.0f}%"
    except (TypeError, ValueError):
        return "0%"


def generar_pdf(cotizacion: Dict[str, Any], salida: Union[str, Path]) -> Path:
    parametros = cotizacion.get("parametros_globales", {})
    partidas = cotizacion.get("partidas", [])
    resumen = cotizacion.get("resumen_financiero", {})

    filas = []
    for item in partidas:
        filas.append(
            "<tr>"
            f"<td>{escape(str(item.get('sku', '')))}</td>"
            f"<td>{escape(str(item.get('descripcion', '')))}</td>"
            f"<td class='center'>{escape(str(item.get('unidad', '')))}</td>"
            f"<td class='center'>{item.get('galones_a_comprar', 0)}</td>"
            f"<td class='right'>{_clp(item.get('precio_unitario_neto'))}</td>"
            f"<td class='right'>{_clp(item.get('costo_directo_neto'))}</td>"
            "</tr>"
        )
    cuerpo = "\n".join(filas)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 2cm; }}
  body {{ font-family: 'Liberation Sans', Arial, sans-serif; color: #1e293b; font-size: 12px; }}
  .header {{ border-bottom: 3px solid #1a2a4a; padding-bottom: 10px; margin-bottom: 18px; }}
  .header h1 {{ margin: 0; color: #1a2a4a; font-size: 22px; }}
  .header p {{ margin: 3px 0; color: #475569; }}
  .meta {{ display: flex; justify-content: space-between; margin-bottom: 14px; }}
  .meta div {{ font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th {{ background: #1a2a4a; color: #fff; padding: 8px; text-align: left; font-size: 11px; }}
  td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
  .right {{ text-align: right; }}
  .center {{ text-align: center; }}
  .box {{ background: #f1f5f9; border-radius: 6px; padding: 10px 14px; margin-top: 12px; }}
  .box h3 {{ margin: 0 0 6px 0; font-size: 12px; color: #1a2a4a; }}
  .box p {{ margin: 2px 0; font-size: 11px; }}
  .resumen {{ margin-top: 16px; margin-left: auto; width: 55%; }}
  .resumen td {{ border: none; padding: 5px 8px; }}
  .resumen .total td {{ font-size: 16px; font-weight: bold; color: #0b5e2b; border-top: 2px solid #0b5e2b; }}
  .footer {{ margin-top: 26px; font-size: 9px; color: #64748b; border-top: 1px solid #ddd; padding-top: 8px; }}
</style>
</head>
<body>
  <div class="header">
    <h1>DEPAFIX — COTIZACIÓN DE PINTURA</h1>
    <p>Presupuesto generado automáticamente</p>
  </div>

  <div class="meta">
    <div><strong>Cotización:</strong> {escape(str(cotizacion.get('id_cotizacion', '')))}</div>
    <div><strong>Fecha:</strong> {datetime.now().strftime('%d-%m-%Y %H:%M')}</div>
  </div>

  <div class="meta">
    <div><strong>SKU solicitado:</strong> {escape(str(parametros.get('sku_solicitado', parametros.get('sku', ''))))}</div>
    <div><strong>SKU variante:</strong> {escape(str(parametros.get('sku', '')))}</div>
    <div><strong>Superficie:</strong> {parametros.get('superficie_m2', 0)} m²</div>
  </div>

  <table>
    <thead>
      <tr>
        <th>SKU</th>
        <th>Descripción</th>
        <th class="center">Unidad</th>
        <th class="center">Cantidad</th>
        <th class="right">P. Unit. Neto</th>
        <th class="right">Costo Neto</th>
      </tr>
    </thead>
    <tbody>
      {cuerpo}
    </tbody>
  </table>

  <div class="box">
    <h3>Parámetros de cálculo</h3>
    <p>Rendimiento: {parametros.get('rendimiento_m2_por_galon', 0)} m²/galón · Desperdicio: {_pct(parametros.get('desperdicio_pct'))} · Margen: {_pct(parametros.get('margen_pct'))} · IVA: {_pct(parametros.get('iva_pct'))}</p>
    <p>Precio lista unitario: {_clp(parametros.get('precio_unitario_lista', partidas[0].get('precio_unitario_lista') if partidas else 0))} · Precio neto unitario: {_clp(parametros.get('precio_unitario_neto', partidas[0].get('precio_unitario_neto') if partidas else 0))}</p>
  </div>

  <table class="resumen">
    <tr><td>Costo directo neto</td><td class="right">{_clp(resumen.get('costo_directo_neto_total'))}</td></tr>
    <tr><td>Precio venta neto</td><td class="right">{_clp(resumen.get('precio_venta_neto_total'))}</td></tr>
    <tr><td>IVA (19%)</td><td class="right">{_clp(resumen.get('iva_total'))}</td></tr>
    <tr class="total"><td>TOTAL</td><td class="right">{_clp(resumen.get('precio_venta_con_iva_total'))}</td></tr>
  </table>

  <div class="footer">
    Fuente de precio: {escape(str(parametros.get('precio_fuente_url') or 'Supabase / precios_historial'))}<br>
    Fecha de scrapeo: {escape(str(parametros.get('precio_fecha_scrapeo') or ''))} · Documento generado por DepaFix.
  </div>
</body>
</html>"""

    destino = Path(salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(str(destino), "w+b") as result_file:
        pisa.CreatePDF(src=html, dest=result_file, encoding="utf-8")
    return destino
