import streamlit as st
import pandas as pd
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "https://depafix-presupuestos-production.up.railway.app")
HEADERS = {"X-API-Key": os.getenv("DEPAFIX_API_KEY", "")}

st.set_page_config(page_title="DepaFix 3.0 Dashboard", page_icon="🏗️", layout="wide")

st.title("🏗️ DepaFix 3.0 — Panel Operativo y Cotizaciones")
st.sidebar.header("Menú Táctico")

menu = st.sidebar.selectbox(
    "Selecciona un Módulo",
    ["Cotizaciones en Vivo", "Buscador RAG (Conocimiento)", "Estado Infraestructura"]
)

if menu == "Cotizaciones en Vivo":
    st.subheader("📋 Gestión de Cotizaciones y Obras (Producción)")
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.markdown("### Nueva Cotización")
        with st.form("form_cotizacion", clear_on_submit=True):
            direccion = st.text_input("Dirección de la Propiedad", placeholder="Ej: Av. Providencia 2000, Of. 302")
            desc_item = st.text_input("Descripción de la Partida", placeholder="Ej: Mantención eléctrica preventiva")
            precio = st.number_input("Precio Neto ($)", min_value=0, step=10000, value=150000)
            submit = st.form_submit_button("Guardar en Producción")
            
            if submit:
                if not direccion or not desc_item:
                    st.warning("Completa la dirección y la descripción de la partida.")
                else:
                    payload = {
                        "direccion": direccion,
                        "items": [{"desc": desc_item, "precio": float(precio)}],
                        "total_neto": float(precio)
                    }
                    try:
                        res = requests.post(f"{API_URL}/api/v1/cotizaciones/", json=payload, headers=HEADERS, timeout=10)
                        if res.status_code in [200, 201]:
                            st.success("¡Cotización registrada con éxito en Railway!")
                        else:
                            st.error(f"Error {res.status_code}: {res.text}")
                    except Exception as e:
                        st.error(f"Error de red: {e}")

    with col2:
        st.markdown("### Historial en Supabase")
        try:
            res_list = requests.get(f"{API_URL}/api/v1/cotizaciones/", headers=HEADERS, timeout=10)
            if res_list.status_code == 200:
                cotizaciones = res_list.json().get("data", [])
                if cotizaciones:
                    st.dataframe(pd.DataFrame(cotizaciones), use_container_width=True)
                else:
                    st.info("No hay cotizaciones registradas todavía.")
            else:
                st.error(f"Error {res_list.status_code}: {res_list.text}")
        except Exception as e:
            st.error(f"Error de red: {e}")

elif menu == "Buscador RAG (Conocimiento)":
    st.subheader("🧠 Consulta Vectorial al Cerebro DepaFix")
    query = st.text_input("Consulta técnica (Supabase, Railway, Obras, etc.):")
    if st.button("Buscar en Masterclasses") and query:
        try:
            res_rag = requests.post(f"{API_URL}/api/v1/rag/buscar", json={"consulta": query, "match_count": 3}, headers=HEADERS, timeout=15)
            if res_rag.status_code == 200:
                st.json(res_rag.json())
            else:
                st.error(f"Error RAG ({res_rag.status_code}): {res_rag.text}")
        except Exception as e:
            st.error(f"Error de red: {e}")

elif menu == "Estado Infraestructura":
    st.subheader("☁️ Monitoreo en Tiempo Real")
    try:
        health = requests.get(f"{API_URL}/health", headers=HEADERS, timeout=5)
        if health.status_code == 200:
            st.success(f"Backend Railway Online: {health.json()}")
        else:
            st.error(f"Alerta en Railway: HTTP {health.status_code}")
    except Exception as e:
        st.error(f"Backend inaccesible: {e}")
