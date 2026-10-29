import pandas as pd
import os
import re

# Ruta del Excel
excel_path = "/home/ibar/Descargas/Documentos/Lista 300 (4).xlsx"
# Ruta de destino
dest_dir = os.path.expanduser("~/gantt/en/analisis/")

# Asegurar que la carpeta existe
os.makedirs(dest_dir, exist_ok=True)

try:
    # Leer la hoja Prospectos
    df = pd.read_excel(excel_path, sheet_name="Prospectos")
    
    # Los números que necesitamos
    numeros = [124, 125, 126, 127, 128]
    
    # Filtrar el dataframe
    df_filtrado = df[df['N°'].isin(numeros)]
    
    if df_filtrado.empty:
        print("No se encontraron los prospectos 124 al 128 en la hoja 'Prospectos'.")
    else:
        for index, row in df_filtrado.iterrows():
            num = int(row['N°'])
            nombre = str(row['Nombre']).strip()
            rubro = str(row['Rubro']) if pd.notna(row['Rubro']) else ""
            vinculo = str(row['Vínculo']) if pd.notna(row['Vínculo']) else ""
            
            # Crear nombre de archivo seguro (ej: paulina_lamatta.md)
            nombre_archivo = re.sub(r'[^a-z0-9]', '_', nombre.lower()) + ".md"
            ruta_archivo = os.path.join(dest_dir, nombre_archivo)
            
            # Plantilla
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
            # Escribir el archivo
            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                f.write(plantilla)
                
            print(f"Creado: {nombre_archivo}")
            
    print("¡Proceso completado!")
            
except Exception as e:
    print(f"Error: {e}")
