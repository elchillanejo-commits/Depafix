import requests
import os

# Endpoint en producción
URL = "https://ikki-api-production.up.railway.app/api/v1/simular"

# AQUÍ PONES TU LISTA DE PROSPECTOS (Mañana cambias estos nombres)
PROSPECTOS = [
    {"cliente_id": "ferreteria_lopez", "rubro": "construccion", "presupuesto_pauta": 200000},
    {"cliente_id": "clinica_dental_smile", "rubro": "salud", "presupuesto_pauta": 400000},
    {"cliente_id": "corredora_propiedades_sur", "rubro": "inmobiliaria", "presupuesto_pauta": 600000},
]

print(f"🎯 Iniciando Modo Francotirador: {len(PROSPECTOS)} reportes a generar...\n")

for p in PROSPECTOS:
    print(f"Generando reporte para: {p['cliente_id']}...")
    response = requests.post(URL, json=p)
    
    if response.status_code == 200:
        data = response.json()["campaña_generada"]
        fee = data["configuracion"]["fee_calculado"]
        copys = data["configuracion"]["copys_generados"]

        # Generar HTML
        copys_html = ""
        for i, copy in enumerate(copys, 1):
            copys_html += f"""
            <div style="border: 1px solid #eee; border-radius: 8px; padding: 20px; margin-bottom: 20px; background: #fafafa;">
                <span style="background: #000; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Opción {i}</span>
                <h3 style="margin-top: 10px; font-size: 18px;">{copy['titulo']}</h3>
                <p style="color: #555;">{copy['cuerpo']}</p>
                <button style="background: #0066ff; color: #fff; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold;">{copy['cta']}</button>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Propuesta - {p['cliente_id']}</title></head>
<body style="font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 40px;">
    <div style="max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08);">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 20px; margin-bottom: 30px;">
            <h1 style="margin: 0;">Propuesta de Campaña Digital</h1>
            <p>Preparado para: <strong>{p['cliente_id'].replace('_', ' ').title()}</strong> ({p['rubro'].title()})</p>
        </div>
        <div style="display: flex; justify-content: space-between; background: #000; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 40px;">
            <div><span style="display:block; font-size:12px; color:#aaa;">Pauta Meta Ads</span><strong>${fee['pauta_neta']:,}</strong></div>
            <div><span style="display:block; font-size:12px; color:#aaa;">Fee Agencia</span><strong>${fee['fee_fijo']:,}</strong></div>
            <div><span style="display:block; font-size:12px; color:#aaa;">Comisión</span><strong>${fee['comision_agencia']:,}</strong></div>
            <div><span style="display:block; font-size:12px; color:#aaa;">Inversión Total</span><strong style="color: #00ffcc;">${fee['total_facturar_clp']:,}</strong></div>
        </div>
        <h2>Propuestas de Anuncios</h2>
        {copys_html}
        <p style="text-align: center; margin-top: 40px; font-size: 12px; color: #888;">Generado automáticamente por Ikki Agency.</p>
    </div>
</body>
</html>"""

        # Guardar en carpeta de reportes
        os.makedirs("reportes_generados", exist_ok=True)
        filename = f"reportes_generados/propuesta_{p['cliente_id']}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"  ✅ Guardado: {filename}")
    else:
        print(f"  ❌ Error con {p['cliente_id']}")

print("\n🏁 Proceso masivo completado. Revisa la carpeta 'reportes_generados/'.")
