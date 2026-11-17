import os, math, pandas as pd, streamlit as st, urllib.parse
from datetime import date
from io import BytesIO

# Detectamos si estamos en la nube (Streamlit Cloud) o en la laptop (Local)
try:
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
except:
    pass

if not os.getenv("SUPABASE_URL"):
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
else:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="DepaFix · Visitas Pro", layout="wide")

# --- BLOQUEO DE SEGURIDAD ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acceso Restringido")
    st.write("Por favor, ingresa la contraseña para acceder al sistema.")
    password = st.text_input("Contraseña:", type="password")
    if st.button("Ingresar"):
        # Cambia "DepaFix2026" por la contraseña que tu quieras
        if password == "DepaFix2026":
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()
# ----------------------------

st.title("🏠 DepaFix · Sistema Predictivo de Visitas")

@st.cache_data(ttl=30)
def cargar_propiedades():
    resp = supabase.table("propiedades_v1").select("id,direccion,comuna,estado,anio_construccion").order("direccion").execute()
    return pd.DataFrame(resp.data)

df_props = cargar_propiedades()
if df_props.empty: st.error("Base de datos vacía."); st.stop()

df_props["antiguedad"] = 2026 - df_props["anio_construccion"].fillna(2026)

menu = st.sidebar.radio("Navegación:", ["Registrar Visita", "Agenda y Mapas", "Lista de Compras", "Comunas"])

if menu == "Registrar Visita":
    st.header("📝 Auditoría y Registro en Terreno")
    opciones = df_props.apply(lambda r: f"[{r['id']}] {r['direccion']} · {r['comuna']} (Edificio: {r['anio_construccion'] or 'S/I'})", axis=1).tolist()
    idx = st.selectbox("Seleccionar Propiedad:", range(len(opciones)), format_func=lambda i: opciones[i])
    prop = df_props.iloc[idx]
    
    # Lógica predictiva
    antiguedad = prop['antiguedad']
    sugerencia_alfombra = " (Alerta: Edificio antiguo, probable cambio a piso flotante)" if antiguedad >= 20 else ""
    
    st.info(f"**Propiedad ID:** {prop['id']} | **Dirección:** {prop['direccion']} | **Comuna:** {prop['comuna']}")
    
    # Mapa directo
    query = urllib.parse.quote(f"{prop['direccion']}, {prop['comuna']}, Chile")
    st.markdown(f"[🗺️ Abrir ruta en Google Maps](https://www.google.com/maps/search/?api=1&query={query})")

    with st.form("form_visita"):
        st.subheader("🔧 Inventario Técnico")
        c1, c2 = st.columns(2)
        with c1:
            # Si es antiguo, sugerimos marcar la casilla
            pintura = st.checkbox("¿Necesita pintura?")
            termo = st.checkbox("¿Tiene termo?")
            alfombra = st.checkbox(f"¿Tiene alfombra?{sugerencia_alfombra}")
        with c2:
            griferia = st.checkbox("¿Necesita griferías?")
            enchufes = st.checkbox("¿Necesita enchufes?")
            cortinas = st.checkbox("¿Ofrecer cortinas roller?")
            
        # Partidas de renovación
        st.subheader("🏗️ Partidas de Renovación")
        cambio_piso = st.checkbox("¿Requiere cambio de piso flotante?")
        
        st.subheader("📅 Datos de la Visita")
        fecha = st.date_input("Fecha:", date.today())
        obs = st.text_area("Observaciones:")
        
        if st.form_submit_button("Guardar Visita"):
            try:
                supabase.table("inventario_tecnico").upsert({
                    "propiedad_id": int(prop["id"]),
                    "necesita_pintura": pintura,
                    "tiene_termo": termo,
                    "tiene_alfombra": alfombra,
                    "necesita_griferias": griferia,
                    "cambio_piso_flotante": cambio_piso,
                    "ofrecer_cortinas": cortinas
                }, on_conflict="propiedad_id").execute()
                
                supabase.table("registro_visitas").insert({
                    "propiedad_id": int(prop["id"]),
                    "fecha_visita": str(fecha),
                    "observaciones": obs
                }).execute()
                st.success("✅ Datos guardados correctamente"); st.cache_data.clear()
            except Exception as e: st.error(f"Error: {e}")

elif menu == "Agenda y Mapas":
    st.header("📅 Agenda de Visitas Programadas")
    st.markdown("Organiza tus visitas y abre la ruta exacta en Google Maps para ahorrar tiempo en traslados.")
    
    # Aquí mostraremos las visitas registradas (con opción a ver el mapa)
    try:
        res = supabase.table("registro_visitas").select("*").order("fecha_visita").execute()
        v = pd.DataFrame(res.data)
        if not v.empty:
            v = v.merge(df_props[["id","direccion","comuna"]], left_on="propiedad_id", right_on="id")
            for _, row in v.iterrows():
                query = urllib.parse.quote(f"{row['direccion']}, {row['comuna']}, Chile")
                st.markdown(f"📅 **{row['fecha_visita']}** - {row['direccion']} ([🗺️ Ver Mapa](https://www.google.com/maps/search/?api=1&query={query}))")
    except Exception as e: st.error(e)

elif menu == "Lista de Compras":
    st.header("🛒 Lista de Compras Consolidada")
    inv = pd.DataFrame(supabase.table("inventario_tecnico").select("*").execute().data)
    if not inv.empty:
        inv = inv.merge(df_props[["id","direccion","comuna"]], left_on="propiedad_id", right_on="id")
        st.dataframe(inv[["direccion","comuna","necesita_pintura","necesita_griferias","cambio_piso_flotante","ofrecer_cortinas"]], use_container_width=True, hide_index=True)
        st.info("💡 Aquí puedes filtrar y ver cuántos pisos flotantes necesitas comprar en total.")

elif menu == "Comunas":
    st.header("📍 Propiedades por Comuna")
    st.dataframe(df_props.groupby("comuna").size().reset_index(name="Total").sort_values("Total", ascending=False), use_container_width=True)
