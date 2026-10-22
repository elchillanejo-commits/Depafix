import streamlit as st
import requests
import pandas as pd
import io
import zipfile
import os
import urllib.parse
import sys
from pathlib import Path
from supabase import create_client
from dotenv import load_dotenv
from xhtml2pdf import pisa

# Parche de rutas para Streamlit Cloud
_AGENCIA_DIR = Path(__file__).resolve().parent
if str(_AGENCIA_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENCIA_DIR))

from meta_ads_integrator import MetaAdsIntegrator

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL:
    try:
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
        SUPABASE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    except Exception:
        pass

API_URL = "https://ikki-api-production.up.railway.app"

st.set_page_config(page_title="Ikki Agency - Growth System", page_icon="🚀", layout="wide")
st.title("🚀 Ikki Agency - Panel de Control")

def generar_html(data, cliente, rubro):
    fee = data["configuracion"]["fee_calculado"]
    copys = data["configuracion"]["copys_generados"]
    benchmarks = data["configuracion"].get("benchmarks_mercado", {})
    proyecciones = data["configuracion"].get("proyecciones", {})
    caso_exito = data["configuracion"].get("caso_exito", {})
    plan_vuelo = data["configuracion"].get("plan_vuelo", [])
    
    plataforma = benchmarks.get("plataforma_recomendada", "Meta Ads")
    justificacion = benchmarks.get("justificacion", "Estrategia estándar.")
    impresiones = f"{proyecciones.get('impresiones_estimadas', 0):,}".replace(",", ".")
    clics = f"{proyecciones.get('clics_estimados', 0):,}".replace(",", ".")

    plan_vuelo_html = ""
    if plan_vuelo:
        plan_vuelo_html = "<h2>🗓️ Plan de Vuelo (30 Días)</h2><table style='width:100%; border-collapse:collapse; font-size:13px; margin-bottom:20px;'>"
        for paso in plan_vuelo:
            plan_vuelo_html += f"<tr><td style='padding:8px; border-bottom:1px solid #eee; font-weight:bold; color:#0066ff;'>{paso['semana']}</td><td style='padding:8px; border-bottom:1px solid #eee;'>{paso['accion']}</td></tr>"
        plan_vuelo_html += "</table>"

    copys_html = "".join([f"<div style='border:1px solid #eee;padding:20px;margin-bottom:20px;background:#fafafa;border-radius:8px;'><span style='background:#000;color:#fff;padding:4px 8px;border-radius:4px;font-size:12px;'>Opción {i}</span><h3 style='margin-top:10px;font-size:18px;'>{c['titulo']}</h3><p style='color:#555;'>{c['cuerpo']}</p><button style='background:#0066ff;color:#fff;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;'>{c['cta']}</button></div>" for i, c in enumerate(copys, 1)])

    # Bloque de Caso de Éxito
    caso_html = ""
    if caso_exito:
        caso_html = f"""
        <h2>📈 Caso de Éxito Comprobado</h2>
        <div style='border:1px solid #d6e4ff; border-left:5px solid #0066ff; background:#f5f9ff; padding:20px 24px; border-radius:8px; margin-bottom:20px;'>
            <p style='margin:0 0 14px 0; color:#333; font-size:13px;'>{caso_exito.get('descripcion', '')}</p>
            <table style='width:100%; border-collapse:collapse; font-size:13px;'>
                <tr><td style='padding:6px 0; color:#666; width:45%;'>CPL promedio</td><td style='padding:6px 0; color:#000; font-weight:bold;'>${caso_exito.get('cpl_promedio_clp', 0):,} CLP</td></tr>
                <tr><td style='padding:6px 0; color:#666;'>Creatividad recomendada</td><td style='padding:6px 0; color:#000; font-weight:bold;'>{caso_exito.get('mejor_creatividad', '')}</td></tr>
                <tr><td style='padding:6px 0; color:#666;'>Fuente</td><td style='padding:6px 0; color:#333;'>{caso_exito.get('fuente', '')}</td></tr>
            </table>
        </div>
        """
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
        body {{ font-family: Arial; background: #f4f7f6; padding: 40px; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
        .header {{ text-align: center; border-bottom: 2px solid #000; margin-bottom: 30px; }}
        .financials {{ display: flex; justify-content: space-between; background: #000; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
        .financials span {{ font-size: 12px; color: #aaa; display: block; }} .financials strong {{ font-size: 20px; }}
        .projections {{ display: flex; gap: 20px; margin-bottom: 30px; }}
        .proj-card {{ flex: 1; background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #ddd; text-align: center; }}
        .proj-card h4 {{ margin: 0 0 10px 0; color: #333; }}
        .proj-card .number {{ font-size: 24px; font-weight: bold; color: #0066ff; }}
        .justification {{ font-size: 13px; color: #666; margin-top: 10px; font-style: italic; }}
        h2 {{ border-bottom: 1px solid #eee; padding-bottom: 10px; }}
    </style></head><body><div class="container">
        <div class="header" style="text-align:left;">
            <h1 style="font-size:36px; margin-bottom:5px;">Propuesta de Marketing Digital</h1>
            <p style="color:#666; font-size:14px; margin-bottom:30px;">Preparado exclusivamente para: <strong>{cliente.replace('_', ' ').title()}</strong> | Fecha: {data.get('fecha_inicio', '')}</p>
            <hr style="border:1px solid #eee; margin-bottom:20px;">
            <h3 style="color:#333;">Resumen Ejecutivo</h3>
            <p style="color:#555; font-size:14px; line-height:1.5;">Esta propuesta detalla la estrategia de adquisición de clientes para el rubro <strong>{rubro}</strong>. Basado en nuestro análisis de mercado, recomendamos concentrar los esfuerzos en <strong>{plataforma}</strong> para maximizar el retorno de la inversión (ROI). El presupuesto de <strong>${fee['pauta_neta']:,} CLP</strong> generará una proyección de <strong>{impresiones} impresiones</strong> y <strong>{clics} clics</strong> en los próximos 30 días.</p>
        </div>
        
        <div class="financials">
            <div><span>Pauta Meta Ads</span><strong>${fee['pauta_neta']:,}</strong></div>
            <div><span>Fee Agencia</span><strong>${fee['fee_fijo']:,}</strong></div>
            <div><span>Comisión (15%)</span><strong>${fee['comision_agencia']:,}</strong></div>
            <div><span>Inversión Total</span><strong style="color: #00ffcc;">${fee['total_facturar_clp']:,}</strong></div>
        </div>

        <h2>Estrategia y Proyecciones Reales (2026)</h2>
        <div class="projections">
            <div class="proj-card">
                <h4>Plataforma Recomendada</h4>
                <div class="number">{plataforma}</div>
                <div class="justification">{justificacion}</div>
            </div>
            <div class="proj-card">
                <h4>Impresiones Estimadas</h4>
                <div class="number">{impresiones}</div>
                <div class="justification">Basado en CPM real del mercado.</div>
            </div>
            <div class="proj-card">
                <h4>Clics Estimados</h4>
                <div class="number">{clics}</div>
                <div class="justification">Tráfico potencial a tu sitio.</div>
            </div>
        </div>

        {caso_html}

        <h2>Propuestas de Anuncios</h2>
        {plan_vuelo_html}
        {copys_html}
        <p style="text-align: center; margin-top: 40px; font-size: 12px; color: #888;">Ikki Agency.</p>
    </div></body></html>"""

def generar_pdf(html_content):
    result = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html_content), dest=result)
    return result.getvalue()

tab1, tab2, tab3 = st.tabs(["🎯 Generador Rápido", "📦 Prospección Masiva", "📊 Gestión de Ventas (CRM)"])

with tab1:
    st.header("Generar Propuesta Individual")
    col_a, col_b, col_c = st.columns(3)
    with col_a: cliente_id = st.text_input("Nombre del Cliente", "inmobiliaria_central")
    with col_b: rubro = st.text_input("Rubro", "inmobiliaria")
    with col_c: presupuesto = st.number_input("Presupuesto Pauta (CLP)", min_value=50000, value=300000, step=50000)
    
    if st.button("⚡ Generar Campaña", type="primary", key="btn_gen"):
        res = requests.post(f"{API_URL}/api/v1/simular", json={"cliente_id": cliente_id, "rubro": rubro, "presupuesto_pauta": int(presupuesto)})
        if res.status_code == 200:
            data = res.json()["campaña_generada"]
            fee = data["configuracion"]["fee_calculado"]
            st.success("¡Campaña generada y guardada!")
            c1, c2 = st.columns(2)
            c1.metric("Pauta", f"${fee['pauta_neta']:,}")
            c2.metric("Total", f"${fee['total_facturar_clp']:,}")
            
            html_data = generar_html(data, cliente_id, rubro)
            pdf_data = generar_pdf(html_data)
            
            st.download_button("📥 Descargar PDF", pdf_data, file_name=f"Propuesta_{cliente_id}.pdf", mime="application/pdf", type="primary", key="btn_pdf")
            st.download_button("📥 Descargar HTML", html_data, file_name=f"prop_{cliente_id}.html", mime="text/html", key="btn_html")
            
            st.divider()
            if st.button("🚀 Crear en Meta Ads (Sandbox)", type="secondary", key="btn_meta"):
                try:
                    integrador = MetaAdsIntegrator()
                    respuesta = integrador.crear_campana_sandbox(data)
                    st.success(f"✅ Campaña creada en Meta. ID: {respuesta['campaign_id']} (Estado: {respuesta['status']})")
                except Exception as e:
                    st.error(f"Error al conectar con Meta: {e}")

with tab2:
    st.header("Prospección Masiva (CSV)")
    uploaded_file = st.file_uploader("Sube tu CSV (cliente_id, rubro, presupuesto_pauta)", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df, width="stretch")
        
        if st.button("⚡ Generar Reportes Masivos (PDFs)", type="primary", key="btn_masivo"):
            zip_buffer = io.BytesIO()
            progress_bar = st.progress(0)
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for idx, row in df.iterrows():
                    payload = {"cliente_id": str(row['cliente_id']), "rubro": str(row['rubro']), "presupuesto_pauta": int(row['presupuesto_pauta'])}
                    res = requests.post(f"{API_URL}/api/v1/simular", json=payload)
                    if res.status_code == 200:
                        html_content = generar_html(res.json()["campaña_generada"], payload['cliente_id'], payload['rubro'])
                        pdf_data = generar_pdf(html_content)
                        zip_file.writestr(f"propuesta_{payload['cliente_id']}.pdf", pdf_data)
                    progress_bar.progress((idx + 1) / len(df))
            st.success(f"¡{len(df)} reportes PDF generados!")
            st.download_button("📥 Descargar ZIP con PDFs", zip_buffer.getvalue(), file_name="reportes_ikki_pdf.zip", mime="application/zip", type="primary", key="btn_zip")

with tab3:
    st.header("Gestión de Prospectos (CRM)")
    if SUPABASE_URL and SUPABASE_KEY:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = client.table("campanas_meta").select("id", "cliente_id", "presupuesto_total", "estado").execute()
        if res.data:
            df_crm = pd.DataFrame(res.data).rename(columns={"cliente_id": "Cliente", "presupuesto_total": "Pauta (CLP)", "estado": "Estado"})
            def calcular_score(row):
                base = 50
                bonus_pauta = row["Pauta (CLP)"] / 10000
                estado = row["Estado"]
                bonus_estado = {"BORRADOR": 0, "ENVIADO": 10, "RESPONDIO": 25, "CERRADO": 40}.get(estado, 0)
                return int(base + bonus_pauta + bonus_estado)
            df_crm["Score"] = df_crm.apply(calcular_score, axis=1)
            mensaje_base = "Hola! Te escribo de Agencia Ikki. Vi tu negocio y preparé un reporte gratuito con 3 opciones de anuncios para tu rubro. ¿Te gustaría que te lo envíe por aquí para que lo revises sin compromiso?"
            df_crm["Contactar"] = f"https://wa.me/?text={urllib.parse.quote(mensaje_base)}"
            edited_df = st.data_editor(
                df_crm,
                column_config={
                    "Estado": st.column_config.SelectboxColumn("Estado", options=["BORRADOR", "ENVIADO", "RESPONDIO", "CERRADO"], required=True),
                    "Contactar": st.column_config.LinkColumn("Acción", display_text="💬 Enviar Pitch")
                },
                disabled=["id", "Cliente", "Pauta (CLP)", "Score", "Contactar"], hide_index=True, width="stretch"
            )
            col_save, col_export = st.columns(2)
            with col_save:
                if st.button("💾 Guardar Cambios", type="primary", key="btn_crm"):
                    cambios = 0
                    for index, row in edited_df.iterrows():
                        if row["Estado"] != df_crm.iloc[index]["Estado"]:
                            client.table("campanas_meta").update({"estado": row["Estado"]}).eq("id", row["id"]).execute()
                            cambios += 1
                    if cambios > 0: st.success(f"¡Se actualizaron {cambios} prospectos!")
                    else: st.info("No hubo cambios.")
            with col_export:
                csv = edited_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Exportar CRM a CSV", data=csv, file_name='ikki_crm_export.csv', mime='text/csv', key="btn_csv")
        else: 
            st.info("Sin prospectos.")
