import requests
import json
import os

URL = "https://ikki-api-production.up.railway.app/api/v1/simular"
PROSPECTO = {
    "cliente_id": "cafeteria_don_pepe",
    "rubro": "gastronomia",
    "presupuesto_pauta": 300000
}

print(f"🤖 Generando reporte HTML para: {PROSPECTO['cliente_id']}...\n")
response = requests.post(URL, json=PROSPECTO)

if response.status_code == 200:
    data = response.json()["campaña_generada"]
    fee = data["configuracion"]["fee_calculado"]
    copys = data["configuracion"]["copys_generados"]

    # Generar las tarjetas de los copys
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
            <p>Preparado para: <strong>{PROSPECTO['cliente_id'].replace('_', ' ').title()}</strong> ({PROSPECTO['rubro'].title()})</p>
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

    with open("reporte_ikki.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("✅ Reporte HTML generado exitosamente.")
    print("📂 Abriendo en el navegador...")
    os.system("xdg-open reporte_ikki.html")
else:
    print(f"❌ Error: {response.status_code}")
