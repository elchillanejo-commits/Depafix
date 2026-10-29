import pandas as pd
import os

# Buscar el archivo en varias ubicaciones posibles
posibles_rutas = [
    "prospectos.csv",
    "Lista 300 (FINAL).xlsx",
    "/home/ibar/gantt/datos/prospectos_300.tsv",
    "datos/prospectos_300.tsv"
]

TSV_PATH = None
for ruta in posibles_rutas:
    if os.path.exists(ruta):
        TSV_PATH = ruta
        print(f"✅ Archivo encontrado: {ruta}")
        break

if not TSV_PATH:
    print("❌ No se encontró ningún archivo de prospectos.")
    print("Busca el archivo y colócalo en esta carpeta.")
    exit(1)

def llenar():
    # Leer según el formato
    if TSV_PATH.endswith('.csv'):
        df = pd.read_csv(TSV_PATH, dtype=str)
    elif TSV_PATH.endswith('.xlsx'):
        df = pd.read_excel(TSV_PATH, dtype=str)
    else:
        df = pd.read_csv(TSV_PATH, sep='\t', dtype=str)
    
    df = df.fillna('')
    
    print(f"📋 Archivo: {TSV_PATH}")
    print(f"📊 Total filas: {len(df)}")
    print(f"📋 Columnas: {list(df.columns)}\n")
    
    # Recorrer y preguntar
    for idx, row in df.iterrows():
        nombre = row.get('Nombre', 'Desconocido')
        if pd.isna(nombre) or str(nombre).strip() == '':
            continue
            
        # Revisar si tiene algún campo vacío o con '?'
        campos_vacios = [col for col in df.columns if str(row[col]).strip() in ['', '?', 'nan']]
        if not campos_vacios:
            continue
            
        print(f"\n{'='*50}")
        print(f"👤 {nombre}")
        print(f"{'='*50}")
        
        for col in campos_vacios:
            respuesta = input(f"  {col}: ").strip()
            if respuesta:
                df.at[idx, col] = respuesta
        
        continuar = input("\n  ¿Continuar? (S/n): ").strip().lower()
        if continuar == 'n':
            break
    
    # Guardar
    if TSV_PATH.endswith('.csv'):
        df.to_csv(TSV_PATH, index=False)
    elif TSV_PATH.endswith('.xlsx'):
        df.to_excel(TSV_PATH, index=False)
    else:
        df.to_csv(TSV_PATH, sep='\t', index=False)
    
    print(f"\n✅ Guardado en {TSV_PATH}")

if __name__ == "__main__":
    llenar()
