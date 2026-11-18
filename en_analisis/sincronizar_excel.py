import openpyxl
import os
import re

print("Sincronizando Prospectos -> Fichas y Dossiers...")
wb = openpyxl.load_workbook('Lista 300 (FINAL_COMPLETO).xlsx')
ws_pros = wb['Prospectos']
ws_fichas = wb['Fichas']
ws_doss = wb['Dossiers']

# Mapas de columnas
h_pros = {cell.value: cell.column for cell in ws_pros[1]}
h_fichas = {cell.value: cell.column for cell in ws_fichas[1]}
h_doss = {cell.value: cell.column for cell in ws_doss[1]}

# IDs existentes
exist_fichas = {int(float(row[0])) for row in ws_fichas.iter_rows(min_row=2, max_col=1, values_only=True) if row[0]}
exist_doss = {int(float(row[0])) for row in ws_doss.iter_rows(min_row=2, max_col=1, values_only=True) if row[0]}

# Archivos .md disponibles
md_files = {}
if os.path.exists('en_analisis'):
    for f in os.listdir('en_analisis'):
        if f.endswith('.md'):
            md_files[f.replace('.md', '').lower()] = os.path.join('en_analisis', f)

added_f = 0
added_d = 0

for row in ws_pros.iter_rows(min_row=2, values_only=True):
    if not row[0]: continue
    try: num = int(float(row[0]))
    except: continue
    
    nombre = row[h_pros['Nombre']-1]
    rubro = row[h_pros['Rubro']-1]
    eneatipo = row[h_pros['Eneatipo']-1]
    arquetipo = row[h_pros['Arquetipo']-1]
    
    speech, diagnostico, estrategia, porque = '', '', '', ''
    
    # Buscar en .md si existe
    nombre_clean = re.sub(r'[^a-z0-9]+', '_', str(nombre).lower()).strip('_')
    if nombre_clean in md_files:
        with open(md_files[nombre_clean], 'r', encoding='utf-8') as f:
            txt = f.read()
            m_speech = re.search(r'Speech de WhatsApp:\s*\n?(.*?)(?=\n\n|\Z)', txt, re.DOTALL)
            if m_speech: speech = m_speech.group(1).strip()
            
            m_diag = re.search(r'Diagnóstico:\s*\n?(.*?)(?=\n\nEstrategia:|\Z)', txt, re.DOTALL)
            if m_diag: diagnostico = m_diag.group(1).strip()
            
            m_estra = re.search(r'Estrategia:\s*\n?(.*?)(?=\n\nSpeech de WhatsApp:|\Z)', txt, re.DOTALL)
            if m_estra: estrategia = m_estra.group(1).strip()

    # Agregar a Fichas si falta
    if num not in exist_fichas:
        new_row = [None] * ws_fichas.max_column
        new_row[h_fichas['N°']-1] = num
        new_row[h_fichas['Nombre']-1] = nombre
        new_row[h_fichas['Rubro']-1] = rubro
        new_row[h_fichas['Eneatipo']-1] = eneatipo
        new_row[h_fichas['Arquetipo']-1] = arquetipo
        if 'Speech' in h_fichas: new_row[h_fichas['Speech']-1] = speech
        if 'Porque' in h_fichas: new_row[h_fichas['Porque']-1] = diagnostico
        if 'Estado' in h_fichas: new_row[h_fichas['Estado']-1] = 'Pendiente'
        ws_fichas.append(new_row)
        added_f += 1

    # Agregar a Dossiers si falta
    if num not in exist_doss:
        new_row = [None] * ws_doss.max_column
        new_row[h_doss['N°']-1] = num
        new_row[h_doss['Nombre']-1] = nombre
        new_row[h_doss['Eneatipo']-1] = eneatipo
        new_row[h_doss['Arquetipo']-1] = arquetipo
        if 'Diagnostico_Profundo' in h_doss: new_row[h_doss['Diagnostico_Profundo']-1] = diagnostico
        if 'Estrategia_Clave' in h_doss: new_row[h_doss['Estrategia_Clave']-1] = estrategia
        ws_doss.append(new_row)
        added_d += 1

wb.save('Lista 300 (FINAL_COMPLETO).xlsx')
print(f"✅ Sincronización terminada. Se agregaron {added_f} a Fichas y {added_d} a Dossiers.")
print("Ahora todos los prospectos de la base están unificados.")
