import pandas as pd
import openpyxl

print("Cargando Excel...")
wb = openpyxl.load_workbook('Lista 300 (FINAL_COMPLETO).xlsx')
ws_fichas = wb['Fichas']
cols_f = {cell.value: cell.column for cell in ws_fichas[1]}

# Encontrar filas vacías
vacias = []
for row in range(2, ws_fichas.max_row + 1):
    porque = ws_fichas.cell(row=row, column=cols_f.get('Porque')).value
    if not porque: # Si no tiene "Porque", está vacía
        vacias.append(row)

print(f"Hay {len(vacias)} prospectos sin análisis. Vamos a llenarlos uno por uno.")
print("Presiona Ctrl+C para salir en cualquier momento.\n")

for row in vacias:
    nombre = ws_fichas.cell(row=row, column=cols_f.get('Nombre')).value
    print(f"--- Prospecto: {nombre} ---")
    
    porque = input("Diagnóstico (Porque): ")
    no_decir = input("Qué NO decirle: ")
    si_decir = input("Qué SÍ decirle (Entrada): ")
    speech = input("Speech de WhatsApp: ")
    
    ws_fichas.cell(row=row, column=cols_f.get('Porque')).value = porque
    ws_fichas.cell(row=row, column=cols_f.get('NO_decir')).value = no_decir
    ws_fichas.cell(row=row, column=cols_f.get('SI_decir')).value = si_decir
    ws_fichas.cell(row=row, column=cols_f.get('Speech')).value = speech
    
    print("✅ Guardado.\n")

wb.save('Lista 300 (FINAL_COMPLETO).xlsx')
print("¡Todos los datos han sido guardados en el Excel!")
