import streamlit as st
import requests
import pandas as pd
import io
import zipfile
import os
import urllib.parse
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# --- TRUCO PARA STREAMLIT CLOUD ---
# Si estamos en Streamlit Cloud, carga las variables desde st.secrets
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
    copys_html = "".join([f"<div style='border:1px solid #eee;padding:20px;margin-bottom:20px;background:#fafafa;border-radius:8px;'><span style='background:#000;color:#fff;padding:4px 8px;border-radius:4px;font-size:12px;'>Opción {i}</span><h3 style='margin-top:10px;font-size:18px;'>{c['titulo']}</h3><p style='color:#555;'>{c['cuerpo']}</p><button style='background:#0066ff;color:#fff;border:none;padding:10px 20px;border-radius:5px;font-weight:bold;'>{c['cta']}</button></div>" for i, c in enumerate(copys, 1)])
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
        body {{ font-family: Arial; background: #f4f7f6; padding: 40px; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
        .header {{ text-align: center; border-bottom: 2px solid #000; margin-bottom: 30px; }}
        .financials {{ display: flex; justify-content: space-between; background: #000; color: #fff; padding: 20px; border-radius: 8px; margin-bottom: 40px; }}
        .financials span {{ font-size: 12px; color: #aaa; display: block; }} .financials strong {{ font-size: 20px; }}
    </style></head><body><div class="container">
        <div class="header"><h1>Propuesta de Campaña Digital</h1><p>Para: <strong>{cliente.replace('_', ' ').title()}</strong> ({rubro.title()})</p></div>
        <div class="financials">
            <div><span>Pauta Meta Ads</span><strong>${fee['pauta_neta']:,}</strong></div>
            <div><span>Fee Agencia</span><strong>${fee['fee_fijo']:,}</strong></div>
            <div><span>Comisión (15%)</span><strong>${fee['comision_agencia']:,}</strong></div>
            <div><span>Inversión Total</span><strong style="color: #00ffcc;">${fee['total_facturar_clp']:,}</strong></div>
        </div><h2>Propuestas de Anuncios</h2>{copys_html}
        <p style="text-align: center; margin-top: 40px; font-size: 12px; color: #888;">Ikki Agency.</p>
    </div></body></html>"""

tab1, tab2, tab3 = st.tabs(["🎯 Generador Rápido", "📦 Prospección Masiva", "📊 Gestión de Ventas (CRM)"])

with tab1:
    st.header("Generar Propuesta Individual")
    col_a, col_b, col_c = st.columns(3)
    with col_a: cliente_id = st.text_input("Nombre del Cliente", "inmobiliaria_central")
    with col_b: rubro = st.text_input("Rubro", "inmobiliaria")
    with col_c: presupuesto = st.number_input("Presupuesto Pauta (CLP)", min_value=50000, value=300000, step=50000)
    
    if st.button("⚡ Generar Campaña", type="primary"):
        res = requests.post(f"{API_URL}/api/v1/simular", json={"cliente_id": cliente_id, "rubro": rubro, "presupuesto_pauta": int(presupuesto)})
        if res.status_code == 200:
            data = res.json()["campaña_generada"]
            fee = data["configuracion"]["fee_calculado"]
            st.success("¡Campaña generada y guardada!")
            c1, c2 = st.columns(2)
            c1.metric("Pauta", f"${fee['pauta_neta']:,}")
            c2.metric("Total", f"${fee['total_facturar_clp']:,}")
            st.download_button("📥 Descargar HTML", generar_html(data, cliente_id, rubro), file_name=f"prop_{cliente_id}.html", mime="text/html")

with tab2:
    st.header("Prospección Masiva (CSV)")
    uploaded_file = st.file_uploader("Sube tu CSV (cliente_id, rubro, presupuesto_pauta)", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df, width="stretch")
        if st.button("⚡ Generar Reportes Masivos", type="primary"):
            zip_buffer = io.BytesIO()
            progress_bar = st.progress(0)
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for idx, row in df.iterrows():
                    payload = {"cliente_id": str(row['cliente_id']), "rubro": str(row['rubro']), "presupuesto_pauta": int(row['presupuesto_pauta'])}
                    res = requests.post(f"{API_URL}/api/v1/simular", json=payload)
                    if res.status_code == 200:
                        html_content = generar_html(res.json()["campaña_generada"], payload['cliente_id'], payload['rubro'])
                        zip_file.writestr(f"propuesta_{payload['cliente_id']}.html", html_content)
                    progress_bar.progress((idx + 1) / len(df))
            st.success(f"¡{len(df)} reportes generados!")
            st.download_button("📥 Descargar ZIP", zip_buffer.getvalue(), file_name="reportes_ikki.zip", mime="application/zip", type="primary")

with tab3:
    st.header("Gestión de Prospectos (CRM)")
    if SUPABASE_URL and SUPABASE_KEY:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = client.table("campanas_meta").select("id", "cliente_id", "presupuesto_total", "estado").execute()
        if res.data:
            df_crm = pd.DataFrame(res.data).rename(columns={"cliente_id": "Cliente", "presupuesto_total": "Pauta (CLP)", "estado": "Estado"})
            mensaje_base = "Hola! Te escribo de Agencia Ikki. Vi tu negocio y preparé un reporte gratuito con 3 opciones de anuncios para tu rubro. ¿Te gustaría que te lo envíe por aquí para que lo revises sin compromiso?"
            df_crm["Contactar"] = f"https://wa.me/?text={urllib.parse.quote(mensaje_base)}"
            edited_df = st.data_editor(
                df_crm,
                column_config={
                    "Estado": st.column_config.SelectboxColumn("Estado", options=["BORRADOR", "ENVIADO", "RESPONDIO", "CERRADO"], required=True),
                    "Contactar": st.column_config.LinkColumn("Acción", display_text="💬 Enviar Pitch")
                },
                disabled=["id", "Cliente", "Pauta (CLP)", "Contactar"], hide_index=True, width="stretch"
            )
            if st.button("💾 Guardar Cambios"):
                cambios = 0
                for index, row in edited_df.iterrows():
                    if row["Estado"] != df_crm.iloc[index]["Estado"]:
                        client.table("campanas_meta").update({"estado": row["Estado"]}).eq("id", row["id"]).execute()
                        cambios += 1
                if cambios > 0: st.success(f"¡Se actualizaron {cambios} prospectos!")
                else: st.info("No hubo cambios.")
        else: st.info("Sin prospectos.")
