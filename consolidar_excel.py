import pandas as pd
import os

# Rutas
EXCEL_PATH = "Lista 300 (FINAL).xlsx"
TSV_SALIDA = "datos/prospectos_300.tsv"
CSV_SALIDA = "datos/lista_final.csv"

def consolidar():
    print("📂 Leyendo Excel...")
    if not os.path.exists(EXCEL_PATH):
        print(f"❌ No se encuentra {EXCEL_PATH}. Asegúrate de moverlo a esta carpeta.")
        return

    # Leer hojas
    df_prospectos = pd.read_excel(EXCEL_PATH, sheet_name="Prospectos")
    df_fichas = pd.read_excel(EXCEL_PATH, sheet_name="Fichas")

    print("🔗 Uniendo Prospectos y Fichas...")
    
    # Limpiar nombres de columnas para evitar errores
    df_prospectos.columns = [c.strip() for c in df_prospectos.columns]
    df_fichas.columns = [c.strip() for c in df_fichas.columns]

    # Hacer el merge (cruce) usando el N° o el Nombre
    # Traemos desde Fichas las columnas clave que no están en Prospectos
    columnas_a_traer = ['N°', 'Edad', 'Conozco_desde', 'Ultima_charla', 'Frecuencia', 'Cercania', 
                        'Confianza', 'Base_relacion', 'Nivel_Tenis', 'Red_Contactos', 'Estado_civil', 
                        'Hijos', 'Vive_en', 'Economia', 'Problemas', 'Logros', 'Le_importa', 
                        'Le_molesta', 'Como_decide', 'Riesgo', 'Conoce_gente_plata', 'Circulos', 
                        'Red_util', 'Presenta_gente', 'Le_pedi_algo', 'Me_pidio_algo', 'Pendientes', 
                        'Porque', 'NO_decir', 'SI_decir', 'Speech', 'Estado']
    
    # Filtrar solo las columnas que existen en Fichas para evitar KeyError
    cols_validas = [c for c in columnas_a_traer if c in df_fichas.columns]
    
    # Unir por N° (left join para mantener a los 174 de Prospectos)
    df_merged = pd.merge(df_prospectos, df_fichas[cols_validas], on='N°', how='left', suffixes=('', '_ficha'))

    # Si el Eneatipo o Arquetipo de Prospectos está vacío o es '?', usar el de Fichas
    if 'Eneatipo_ficha' in df_merged.columns:
        df_merged['Eneatipo'] = df_merged['Eneatipo'].fillna(df_merged['Eneatipo_ficha'])
        df_merged['Arquetipo'] = df_merged['Arquetipo'].fillna(df_merged['Arquetipo_ficha'])
        df_merged.drop(columns=['Eneatipo_ficha', 'Arquetipo_ficha'], inplace=True)

    # Si el Speech_clave está vacío, usar el Speech de Fichas
    if 'Speech' in df_merged.columns:
        df_merged['Speech_clave'] = df_merged['Speech_clave'].fillna(df_merged['Speech'])
    
    # Rellenar vacíos con '?'
    df_merged = df_merged.fillna('?')

    print(f"📊 Total de prospectos consolidados: {len(df_merged)}")

    # Guardar en TSV (para Streamlit)
    os.makedirs('datos', exist_ok=True)
    df_merged.to_csv(TSV_SALIDA, sep='\t', index=False)
    print(f"✅ Archivo local guardado en: {TSV_SALIDA}")

    # Guardar en CSV (para subir a Google Sheets)
    df_merged.to_csv(CSV_SALIDA, index=False)
    print(f"✅ Archivo para Google Sheets guardado en: {CSV_SALIDA}")

if __name__ == "__main__":
    consolidar()
