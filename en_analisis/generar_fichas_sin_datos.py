import pandas as pd
import os

print("Buscando prospectos con 'Confianza: baja'...")
df_ia = pd.read_csv('resultados_finales_ia.csv', encoding='utf-8-sig')
sin_ficha = df_ia[df_ia['Confianza'] == 'baja']

print(f"Se encontraron {len(sin_ficha)} prospectos sin ficha para generar.\n")

generados = 0
for _, row in sin_ficha.iterrows():
    nombre = str(row['Nombre'])
    rubro = str(row['Rubro']) if pd.notna(row['Rubro']) else ''
    rol = str(row['Rol']) if pd.notna(row['Rol']) else ''
    vinculo = str(row['Vínculo']) if pd.notna(row['Vínculo']) else ''
    num = int(row['N°'])
    
    # Limpiar nombre para archivo
    import unicodedata, re
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('utf-8').lower()
    archivo_base = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    ruta_md = f"en_analisis/{archivo_base}.md"
    
    if not os.path.exists(ruta_md):
        plantilla = f"""# Perfil: N° {num} - {nombre}
Edad: 
Rubro: {rubro}
Cómo lo conocí: {vinculo}
Hace cuánto: 
Última vez que hablamos: 
Nivel_Tenis: 
Red_de_contactos: 
Personalidad: 
Qué le importa: 
Cómo decide: 
Cómo me trata: 
Su vida (familia, plata, problemas): 
NO decirle: 
Intuición mía: 
"""
        with open(ruta_md, "w", encoding="utf-8") as f:
            f.write(plantilla)
        generados += 1

print(f"✅ Se generaron {generados} archivos vacíos en la carpeta 'en_analisis/'.")
print("\n👉 Para analizarlos con la IA, copia y pega estos comandos uno por uno:")
print("-" * 60)

for _, row in sin_ficha.iterrows():
    nombre = str(row['Nombre'])
    import unicodedata, re
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('utf-8').lower()
    archivo_base = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    print(f"python3 en_analisis/procesar_con_opencode.py {archivo_base}")
