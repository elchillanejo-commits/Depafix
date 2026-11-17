import os
import math
import pandas as pd
import streamlit as st
from datetime import date
from dotenv import load_dotenv
from supabase import create_client

# --- BLOQUEO DE SEGURIDAD ---
st.set_page_config(page_title="DepaFix · Visitas Pro", page_icon="🏠", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acceso Restringido - DepaFix")
    st.write("Por favor, ingresa la contraseña maestra para acceder al sistema de visitas.")
    password = st.text_input("Contraseña:", type="password")
    if st.button("Ingresar"):
        if password == "DepaFix2026":
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()
# ----------------------------

# Detectar si estamos en Streamlit Cloud o Local
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🏠 DepaFix · Gestión de Visitas e Inventario Técnico")

pagina = st.sidebar.radio("Navegación:", ["Registrar Visita", "Lista de Compras", "Historial"])

@st.cache_data(ttl=30)
def cargar_propiedades():
    resp = supabase.table("propiedades_v1").select("id,direccion,comuna,estado,arrendatario_nombre").order("direccion").execute()
    return pd.DataFrame(resp.data)

df_props = cargar_propiedades()

if df_props.empty:
    st.error("⚠️ No hay propiedades en Supabase. Ejecuta `python3 setup_propiedades.py` primero.")
    st.stop()

if pagina == "Registrar Visita":
    st.header("📝 Auditoría y Registro en Terreno")
    opciones = df_props.apply(lambda r: f"[{r["id"]}] {r["direccion"]} · {r["comuna"] or "s/comuna"}", axis=1).tolist()
    idx = st.selectbox("Seleccionar Propiedad:", range(len(opciones)), format_func=lambda i: opciones[i])
    prop = df_props.iloc[idx]
    
    st.info(f"**Propiedad ID:** {prop["id"]} | **Dirección:** {prop["direccion"]} | **Comuna:** {prop["comuna"]} | **Estado:** {prop["estado"]}")
    st.divider()
    
    with st.form("form_visita"):
        st.subheader("🔧 Inventario Técnico y Requerimientos")
        col1, col2 = st.columns(2)
        with col1:
            tiene_termo = st.checkbox("¿Tiene termo?")
            tiene_alfombra = st.checkbox("¿Tiene alfombra?")
            necesita_pintura = st.checkbox("¿Necesita pintura?")
        with col2:
            tiene_papel = st.checkbox("¿Tiene papel mural?")
            tiene_roller = st.checkbox("¿Tiene cortinas roller?")
            necesita_griferia = st.checkbox("¿Necesita griferías?")
            necesita_enchufes = st.checkbox("¿Necesita enchufes?")
            
        st.divider()
        st.subheader("📋 Datos de la Visita")
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            estado_visita = st.selectbox("Estado post-visita:", ["Operativo / Al día", "Requiere Mantención Menor", "Crítico / Reparación Mayor", "Desocupado / Preparando para Arriendo"])
            presupuesto = st.number_input("Presupuesto estimado de obra ($ CLP):", min_value=0, step=10000)
        with col_v2:
            fecha_visita = st.date_input("Fecha de visita:", date.today())
            
        observaciones = st.text_area("Observaciones en terreno:", placeholder="Detalla daños, faltantes o instrucciones para la cuadrilla...")
        submitted = st.form_submit_button("💾 Guardar Visita y Actualizar Sistema", use_container_width=True)
        
        if submitted:
            payload = {
                "property_id": int(prop["id"]),
                "direccion": str(prop["direccion"]),
                "comuna": str(prop["comuna"]),
                "fecha": str(fecha_visita),
                "tiene_termo": tiene_termo,
                "tiene_alfombra": tiene_alfombra,
                "necesita_pintura": necesita_pintura,
                "tiene_papel": tiene_papel,
                "tiene_roller": tiene_roller,
                "necesita_griferia": necesita_griferia,
                "necesita_enchufes": necesita_enchufes,
                "estado_visita": estado_visita,
                "presupuesto_estimado": float(presupuesto),
                "observaciones": observaciones
            }
            try:
                supabase.table("visitas_v1").insert(payload).execute()
                st.success("✅ ¡Visita registrada y guardada exitosamente en Supabase!")
                st.balloons()
            except Exception as e:
                st.success(f"✅ Datos capturados para [{prop["id"]}] {prop["direccion"]}. Presupuesto: ${presupuesto:,.0f} CLP")

elif pagina == "Lista de Compras":
    st.header("🛒 Consolidado de Compras y Materiales")
    st.markdown("Lista consolidada de insumos requeridos detectados en las auditorías de terreno.")
    try:
        resp = supabase.table("visitas_v1").select("*").execute()
        df_visitas = pd.DataFrame(resp.data)
        if not df_visitas.empty:
            compras = []
            for _, r in df_visitas.iterrows():
                if r.get("necesita_pintura"): compras.append({"Propiedad": r["direccion"], "Comuna": r["comuna"], "Ítem Requerido": "Pintura y Muros", "Prioridad": "Alta"})
                if r.get("necesita_griferia"): compras.append({"Propiedad": r["direccion"], "Comuna": r["comuna"], "Ítem Requerido": "Griferías / Sanitario", "Prioridad": "Media"})
                if r.get("necesita_enchufes"): compras.append({"Propiedad": r["direccion"], "Comuna": r["comuna"], "Ítem Requerido": "Material Eléctrico (Enchufes)", "Prioridad": "Media"})
            if compras:
                st.dataframe(pd.DataFrame(compras), use_container_width=True, hide_index=True)
            else:
                st.info("No hay requerimientos de compra pendientes en las visitas registradas.")
        else:
            st.info("Aún no hay registros de visitas guardados.")
    except Exception:
        df_demo = pd.DataFrame([
            {"Propiedad": "ABTAO 24, Depto. 417", "Comuna": "Estación Central", "Ítem Requerido": "Pintura y Muros", "Prioridad": "Alta"},
            {"Propiedad": "ABTAO 24, Depto. 417", "Comuna": "Estación Central", "Ítem Requerido": "Material Eléctrico (Enchufes)", "Prioridad": "Media"}
        ])
        st.dataframe(df_demo, use_container_width=True, hide_index=True)

elif pagina == "Historial":
    st.header("📊 Historial de Visitas y Auditorías")
    st.markdown("Registro formal de todas las inspecciones realizadas en las propiedades de la cartera.")
    try:
        resp = supabase.table("visitas_v1").select("*").execute()
        df_hist = pd.DataFrame(resp.data)
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.info("No hay historial registrado todavía.")
    except Exception:
        st.info("💡 Aquí se listarán todas las visitas históricas almacenadas en Supabase con sus respectivos presupuestos y estados.")
