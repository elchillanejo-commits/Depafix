import pandas as pd
import openpyxl
import os
import re

print("1. Abriendo el Excel...")
wb = openpyxl.load_workbook('Lista 300 (ACTUALIZADA).xlsx')
ws = wb['Prospectos']

# Encontrar columnas
cols = {cell.value: cell.column for cell in ws[1]}
col_eneatipo = cols.get('Eneatipo')
col_arquetipo = cols.get('Arquetipo')

print("2. Buscando archivos .md analizados por la IA...")
actualizados = 0

# Recorremos las filas del Excel
for row_idx in range(2, ws.max_row + 1):
    nombre_cell = ws.cell(row=row_idx, column=2) # Columna B (Nombre)
    if not nombre_cell.value: continue
    
    nombre = str(nombre_cell.value).strip()
    
    # Limpiamos el nombre para buscar el archivo (ej. "Alejandro Bastias" -> "alejandro_bastias")
    s = nombre.lower()
    s = re.sub(r'[áàäâ]', 'a', s)
    s = re.sub(r'[éèëê]', 'e', s)
    s = re.sub(r'[íìïî]', 'i', s)
    s = re.sub(r'[óòöô]', 'o', s)
    s = re.sub(r'[úùüû]', 'u', s)
    nombre_archivo = re.sub(r'[^a-z0-9]+', '_', s).strip('_') + '.md'
    
    ruta_md = f"en_analisis/{nombre_archivo}"
    
    if os.path.exists(ruta_md):
        with open(ruta_md, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
            # Buscamos el Eneatipo y Arquetipo en el texto del análisis
            match_eneatipo = re.search(r'Eneatipo:\s*([1-9]w[1-9])', contenido)
            match_arquetipo = re.search(r'Arquetipo:\s*([A-Za-záéíóúñ]+)', contenido)
            
            if match_eneatipo and match_arquetipo:
                eneatipo = match_eneatipo.group(1)
                arquetipo = match_arquetipo.group(1)
                
                # Actualizamos la celda
                ws.cell(row=row_idx, column=col_eneatipo).value = eneatipo
                ws.cell(row=row_idx, column=col_arquetipo).value = arquetipo
                actualizados += 1

nombre_salida = 'Lista 300 (FINAL).xlsx'
wb.save(nombre_salida)
print(f"\n✅ ¡LISTO! Se actualizaron {actualizados} prospectos con la IA.")
print(f"Archivo guardado como: {nombre_salida}")
