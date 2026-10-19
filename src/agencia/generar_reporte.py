import requests
import argparse
import os
import sys

def generar_reporte(cliente_id, rubro, presupuesto):
    URL = "https://ikki-api-production.up.railway.app/api/v1/simular"
    payload = {
        "cliente_id": cliente_id,
        "rubro": rubro,
        "presupuesto_pauta": presupuesto
    }

    print(f"🤖 Generando reporte para: {cliente_id} ({rubro}) | Pauta: ${presupuesto:,}...\n")
    response = requests.post(URL, json=payload)

    if response.status_code != 200:
        print(f"❌ Error en la API: {response.status_code}")
        sys.exit(1)

    data = response.json()["campaña_generada"]
    fee = data["configuracion"]["fee_calculado"]
    copys = data["configuracion"]["copys_generados"]

    copys_html = ""
    for i, copy in enumerate(copys, 1):
        copys_html += f"""
        <div class="card">
            <span class="tag">Opción {i}</span>
            <h3>{copy['titulo']}</h3>
            <p>{copy['cuerpo']}</p>
            <button class="cta">{copy['cta']}</button>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Propuesta - Ikki Agency</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background-color: #f4f7f6; color: #333; margin: 0; padding: 40px; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
        .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 20px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .financials {{ display: flex; justify-content: space-between; background: #000; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 40px; }}
        .financials div {{ text-align: center; }}
        .financials span {{ display: block; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #aaa; }}
        .financials strong {{ font-size: 20px; }}
        .card {{ border: 1px solid #eee; border-radius: 8px; padding: 20px; margin-bottom: 20px; background: #fafafa; }}
        .card h3 {{ margin-top: 0; font-size: 18px; }}
        .card p {{ color: #555; line-height: 1.5; }}
        .tag {{ background: #000; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
        .cta {{ background: #0066ff; color: #fff; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; margin-top: 10px; }}
        .footer {{ text-align: center; margin-top: 40px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Propuesta de Campaña Digital</h1>
            <p>Preparado para: <strong>{cliente_id.replace('_', ' ').title()}</strong> ({rubro.title()})</p>
        </div>

        <div class="financials">
            <div><span>Pauta Meta Ads</span><strong>${fee['pauta_neta']:,}</strong></div>
            <div><span>Fee Agencia</span><strong>${fee['fee_fijo']:,}</strong></div>
            <div><span>Comisión (15%)</span><strong>${fee['comision_agencia']:,}</strong></div>
            <div><span>Inversión Total</span><strong style="color: #00ffcc;">${fee['total_facturar_clp']:,}</strong></div>
        </div>

        <h2>Propuestas de Anuncios</h2>
        {copys_html}

        <div class="footer">
            Generado automáticamente por Ikki Agency.
        </div>
    </div>
</body>
</html>"""

    filename = f"reporte_{cliente_id}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Reporte guardado en: {filename}")
    os.system(f"xdg-open {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de Propuestas Ikki")
    parser.add_argument("cliente", help="Nombre del cliente (ej: ferreteria_lopez)")
    parser.add_argument("rubro", help="Rubro del negocio (ej: construccion)")
    parser.add_argument("presupuesto", type=int, help="Presupuesto de pauta en CLP (ej: 500000)")
    
    args = parser.parse_args()
    generar_reporte(args.cliente, args.rubro, args.presupuesto)
