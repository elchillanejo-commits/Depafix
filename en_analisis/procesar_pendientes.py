import pandas as pd
import os
import subprocess
import unicodedata
import re

print("Buscando prospectos sin Eneatipo en la hoja Fichas...")
df = pd.read_excel('Lista 300 (FINAL_COMPLETO).xlsx', sheet_name='Fichas')

# Filtramos los que no tienen eneatipo o tienen "?"
pendientes = df[df['Eneatipo'].isna() | (df['Eneatipo'] == '?') | (df['Eneatipo'] == '') | (df['Eneatipo'] == 'Pendiente')]

print(f"Se encontraron {len(pendientes)} prospectos para analizar.\n")

archivos_procesar = []

for _, row in pendientes.iterrows():
    nombre = str(row['Nombre'])
    num = int(row['N°'])
    rubro = str(row['Rubro']) if pd.notna(row['Rubro']) else ''
    
    # Limpiar nombre para archivo
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('utf-8').lower()
    archivo_base = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    ruta_md = f"en_analisis/{archivo_base}.md"
    
    # Creamos el archivo .md con lo que sabemos para que la IA tenga contexto
    plantilla = f"""# Perfil: N° {num} - {nombre}
Rubro: {rubro}
Notas: Prospecto pendiente de análisis.
"""
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(plantilla)
    
    archivos_procesar.append(archivo_base)

print("Iniciando análisis con OpenCode (DeepSeek)...")
print("Esto puede tardar varios minutos. No cierres la terminal.\n")

for i, archivo in enumerate(archivos_procesar, 1):
    ruta_md = f"en_analisis/{archivo}.md"
    print(f"[{i}/{len(archivos_procesar)}] Analizando a: {archivo}...")
    
    comando = f'opencode run "Lee el archivo {ruta_md} y analízalo. Devuélveme el Eneatipo, Arquetipo, Diagnóstico y un Speech de WhatsApp personalizado. Al final, agrega el análisis al final del mismo archivo." --agent build'
    
    try:
        subprocess.run(comando, shell=True, check=False)
        print(f"✅ Completado: {archivo}\n")
    except Exception as e:
        print(f"❌ Error en {archivo}: {e}\n")
        
print("🎉 ¡Proceso completado! Ahora actualiza el Excel.")
