import pandas as pd
import openpyxl

print("1. Leyendo resultados de la IA...")
df_ia = pd.read_csv('resultados_finales_ia.csv', encoding='utf-8-sig')

resultados_dict = {}
for _, row in df_ia.iterrows():
    num = int(float(row['N°']))
    resultados_dict[num] = (row['Eneatipo'], row['Arquetipo'])

print("2. Abriendo el Excel original...")
wb = openpyxl.load_workbook('Lista 300 (4).xlsx')
ws = wb['Prospectos']

col_eneatipo = None
col_arquetipo = None
for col_idx, cell in enumerate(ws[1], start=1):
    if cell.value == 'Eneatipo': col_eneatipo = col_idx
    if cell.value == 'Arquetipo': col_arquetipo = col_idx

print(f"3. Columnas encontradas: Eneatipo (Col {col_eneatipo}), Arquetipo (Col {col_arquetipo})")
print("4. Actualizando celdas...")

actualizados = 0
for row_idx in range(2, ws.max_row + 1):
    id_cell = ws.cell(row=row_idx, column=1) 
    if id_cell.value is None: continue
    
    try:
        num_id = int(float(id_cell.value))
    except ValueError:
        continue 
    
    if num_id in resultados_dict:
        eneatipo, arquetipo = resultados_dict[num_id]
        ws.cell(row=row_idx, column=col_eneatipo).value = eneatipo
        ws.cell(row=row_idx, column=col_arquetipo).value = arquetipo
        actualizados += 1

nombre_salida = 'Lista 300 (ACTUALIZADA).xlsx'
wb.save(nombre_salida)

print(f"\n¡LISTO! Se actualizaron {actualizados} prospectos.")
print(f"Archivo guardado como: {nombre_salida}")
