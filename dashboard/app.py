import streamlit as st
import pandas as pd
import openpyxl
import os

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="DepaFix CRM", page_icon="🎾", layout="wide")

# Ruta absoluta para evitar errores
EXCEL_PATH = "/home/ibar/DepaFix_Maestro/Lista 300 (FINAL_COMPLETO).xlsx"

# --- CARGA DE DATOS ---
@st.cache_data(ttl=5)
def load_data():
    if not os.path.exists(EXCEL_PATH):
        st.error(f"No se encuentra el archivo en: {EXCEL_PATH}")
        return pd.DataFrame()
    df = pd.read_excel(EXCEL_PATH, sheet_name="Fichas")
    return df

df = load_data()

if df.empty:
    st.stop()

# --- SIDEBAR: FILTROS ---
st.sidebar.header("🔍 Filtros")

eneatipos = ["Todos"] + sorted(df['Eneatipo'].dropna().unique().tolist())
filtro_eneatipo = st.sidebar.selectbox("Eneatipo", eneatipos)

rubros = ["Todos"] + sorted(df['Rubro'].dropna().unique().tolist())
filtro_rubro = st.sidebar.selectbox("Rubro", rubros)

busqueda = st.sidebar.text_input("Buscar por Nombre")

# --- APLICAR FILTROS ---
df_filtrado = df.copy()
if filtro_eneatipo != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Eneatipo'] == filtro_eneatipo]
if filtro_rubro != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Rubro'] == filtro_rubro]
if busqueda:
    df_filtrado = df_filtrado[df_filtrado['Nombre'].str.contains(busqueda, case=False, na=False)]

# --- ÁREA PRINCIPAL ---
st.title("🎾 DepaFix CRM - Prospectos")
st.markdown(f"Mostrando **{len(df_filtrado)}** prospectos de {len(df)} totales.")

columnas_tabla = ['N°', 'Nombre', 'Rubro', 'Eneatipo', 'Arquetipo', 'Estado']
st.dataframe(df_filtrado[columnas_tabla], use_container_width=True, hide_index=True)

st.divider()
st.subheader("📋 Ficha del Prospecto")

if not df_filtrado.empty:
    nombres = df_filtrado['Nombre'].tolist()
    seleccionado = st.selectbox("Selecciona un prospecto para ver su ficha completa", nombres)
    
    prospecto = df_filtrado[df_filtrado['Nombre'] == seleccionado].iloc[0]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**Eneatipo:** {prospecto.get('Eneatipo', 'N/A')} / {prospecto.get('Arquetipo', 'N/A')}")
        st.warning(f"**Diagnóstico:**\n{prospecto.get('Porque', 'Sin datos')}")
        st.error(f"**⚠️ Qué NO decirle:**\n{prospecto.get('NO_decir', 'Sin datos')}")
        
    with col2:
        st.success(f"**✅ Qué SÍ decirle:**\n{prospecto.get('SI_decir', 'Sin datos')}")
        st.markdown("### 💬 Speech de WhatsApp")
        speech_texto = prospecto.get('Speech', 'Sin speech generado.')
        st.code(speech_texto, language="text")
        
        st.markdown("### 📌 Estado del Prospecto")
        estados_posibles = ["Pendiente", "Contactado", "Reunión", "Cerrado", "Descartado", "en_análisis"]
        estado_actual = str(prospecto.get('Estado', 'Pendiente'))
        if estado_actual not in estados_posibles:
            estados_posibles.append(estado_actual)
            
        nuevo_estado = st.selectbox("Cambiar estado:", estados_posibles, index=estados_posibles.index(estado_actual))
        
        if st.button("💾 Guardar Estado en Excel"):
            try:
                wb = openpyxl.load_workbook(EXCEL_PATH)
                ws = wb['Fichas']
                col_estado = None
                for cell in ws[1]:
                    if cell.value == 'Estado':
                        col_estado = cell.column
                        break
                
                num_prospecto = int(prospecto['N°'])
                for row in range(2, ws.max_row + 1):
                    if ws.cell(row=row, column=1).value == num_prospecto:
                        ws.cell(row=row, column=col_estado).value = nuevo_estado
                        break
                
                wb.save(EXCEL_PATH)
                st.success(f"Estado actualizado a '{nuevo_estado}'")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
else:
    st.warning("No hay prospectos que coincidan con los filtros.")
