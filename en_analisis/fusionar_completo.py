import pandas as pd
import openpyxl
import os
import re

print("1. Abriendo el Excel...")
wb = openpyxl.load_workbook('Lista 300 (FINAL).xlsx')

# --- Hoja PROSPECTOS (Eneatipo y Arquetipo) ---
ws_pros = wb['Prospectos']
cols_pros = {cell.value: cell.column for cell in ws_pros[1]}
col_eneatipo = cols_pros.get('Eneatipo')
col_arquetipo = cols_pros.get('Arquetipo')

# --- Hoja FICHAS (Speech) ---
ws_fichas = wb['Fichas']
cols_fichas = {cell.value: cell.column for cell in ws_fichas[1]}
col_speech_ficha = cols_fichas.get('Speech')

# --- Hoja DOSSIERS (Diagnóstico y Estrategia) ---
ws_doss = wb['Dossiers']
cols_doss = {cell.value: cell.column for cell in ws_doss[1]}
col_diag = cols_doss.get('Diagnostico_Profundo')
col_estra = cols_doss.get('Estrategia_Clave')

print("2. Procesando archivos .md...")
datos = {}

for archivo in os.listdir('en_analisis'):
    if not archivo.endswith('.md'): continue
    
    ruta = os.path.join('en_analisis', archivo)
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
        
        # Extraer datos con expresiones regulares
        eneatipo = re.search(r'Eneatipo:\s*([1-9]w[1-9])', contenido)
        arquetipo = re.search(r'Arquetipo:\s*([A-Za-záéíóúñ]+)', contenido)
        speech = re.search(r'Speech de WhatsApp:\s*\n?(.*?)(?=\n\n|\Z)', contenido, re.DOTALL)
        diagnostico = re.search(r'Diagnóstico:\s*\n?(.*?)(?=\n\nEstrategia:|\Z)', contenido, re.DOTALL)
        estrategia = re.search(r'Estrategia:\s*\n?(.*?)(?=\n\nSpeech de WhatsApp:|\Z)', contenido, re.DOTALL)
        
        # Limpiar nombre de archivo
        nombre_archivo = archivo.replace('.md', '').lower()
        
        if eneatipo and arquetipo:
            datos[nombre_archivo] = {
                'eneatipo': eneatipo.group(1).strip(),
                'arquetipo': arquetipo.group(1).strip(),
                'speech': speech.group(1).strip() if speech else '',
                'diagnostico': diagnostico.group(1).strip() if diagnostico else '',
                'estrategia': estrategia.group(1).strip() if estrategia else ''
            }

print(f"   Se extrajeron datos de {len(datos)} archivos.")

print("3. Actualizando Excel...")

# Actualizar Prospectos
for row in range(2, ws_pros.max_row + 1):
    nombre_cell = ws_pros.cell(row=row, column=2).value
    if not nombre_cell: continue
    nombre_clean = re.sub(r'[^a-z0-9]+', '_', nombre_cell.lower()).strip('_')
    
    if nombre_clean in datos:
        ws_pros.cell(row=row, column=col_eneatipo).value = datos[nombre_clean]['eneatipo']
        ws_pros.cell(row=row, column=col_arquetipo).value = datos[nombre_clean]['arquetipo']

# Actualizar Fichas (Speech)
for row in range(2, ws_fichas.max_row + 1):
    nombre_cell = ws_fichas.cell(row=row, column=2).value
    if not nombre_cell: continue
    nombre_clean = re.sub(r'[^a-z0-9]+', '_', nombre_cell.lower()).strip('_')
    
    if nombre_clean in datos and col_speech_ficha:
        ws_fichas.cell(row=row, column=col_speech_ficha).value = datos[nombre_clean]['speech']

# Actualizar Dossiers (Diagnóstico y Estrategia)
for row in range(2, ws_doss.max_row + 1):
    nombre_cell = ws_doss.cell(row=row, column=2).value
    if not nombre_cell: continue
    nombre_clean = re.sub(r'[^a-z0-9]+', '_', nombre_cell.lower()).strip('_')
    
    if nombre_clean in datos:
        if col_diag: ws_doss.cell(row=row, column=col_diag).value = datos[nombre_clean]['diagnostico']
        if col_estra: ws_doss.cell(row=row, column=col_estra).value = datos[nombre_clean]['estrategia']

nombre_salida = 'Lista 300 (FINAL_COMPLETO).xlsx'
wb.save(nombre_salida)
print(f"\n✅ ¡LISTO! Archivo guardado como: {nombre_salida}")
print("Ahora sí, ve a la hoja 'Fichas' y 'Dossiers' para ver el análisis completo.")
