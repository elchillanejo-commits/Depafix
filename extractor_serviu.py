import os
import pandas as pd
import yaml
import warnings
from pathlib import Path

# Silenciar advertencias de motores de Excel para mantener la terminal limpia
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", module="pandas")

DIR_CONOCIMIENTO = Path.home() / "Documentos/Conocimiento/01_Tierra_Construccion"
ARCHIVO_YAML = Path.home() / "DepaFix_Maestro/serviu_precios.yml"

def extraer_partidas_excel():
    nuevas_partidas = []
    
    for archivo in DIR_CONOCIMIENTO.rglob("*.xls*"):
        try:
            # Leemos el archivo sin asumir que la fila 1 es el encabezado
            df = pd.read_excel(archivo, header=None)
            
            header_idx = -1
            # Cazador de encabezados: buscar la fila que contenga "item/código" y "precio/valor/total"
            for i, row in df.iterrows():
                row_str = " ".join(str(val).lower() for val in row.values)
                if ("código" in row_str or "codigo" in row_str or "item" in row_str or "ítem" in row_str) and \
                   ("precio" in row_str or "valor" in row_str or "unitario" in row_str or "total" in row_str):
                    header_idx = i
                    break
            
            if header_idx != -1:
                # Asignar la fila encontrada como encabezado real
                df.columns = df.iloc[header_idx].astype(str).str.lower().str.strip()
                df = df.iloc[header_idx+1:] # Cortar todo lo que está arriba del encabezado
                
                col_cod = next((c for c in df.columns if 'cód' in c or 'cod' in c or 'item' in c or 'ítem' in c), None)
                col_pre = next((c for c in df.columns if 'precio' in c or 'valor' in c or 'unitario' in c or 'total' in c), None)
                col_nom = next((c for c in df.columns if 'descrip' in c or 'nombre' in c or 'partida' in c or 'detalle' in c), None)
                col_uni = next((c for c in df.columns if 'unidad' in c or 'unid' in c or 'und' in c), None)

                if col_cod and col_pre:
                    for _, row in df.iterrows():
                        val_cod = str(row.get(col_cod, "")).strip()
                        val_pre = row.get(col_pre)
                        
                        if val_cod and val_cod != 'nan' and pd.notna(val_pre):
                            try:
                                # Limpieza agresiva de formato moneda
                                precio_str = str(val_pre).replace('$', '').replace('.', '').replace(',', '').strip()
                                precio_limpio = int(float(precio_str))
                                
                                if precio_limpio > 0:
                                    partida = {
                                        "codigo": val_cod,
                                        "nombre": str(row.get(col_nom, "Sin descripción")).strip(),
                                        "unidad": str(row.get(col_uni, "un")).strip(),
                                        "precio_unitario": precio_limpio
                                    }
                                    nuevas_partidas.append(partida)
                            except ValueError:
                                continue # Si la celda dice "Subtotal" u otro texto, la salta
        except Exception:
            pass # Modo bruto: Si un excel está corrupto o bloqueado, avanza al siguiente

    return nuevas_partidas

def actualizar_yaml(nuevas_partidas):
    if ARCHIVO_YAML.exists():
        with open(ARCHIVO_YAML, "r", encoding="utf-8") as f:
            datos = yaml.safe_load(f) or {"partidas": []}
    else:
        datos = {"partidas": []}

    codigos_existentes = {str(p['codigo']).strip() for p in datos.get('partidas', [])}
    
    agregados = 0
    for p in nuevas_partidas:
        if p['codigo'] not in codigos_existentes:
            datos['partidas'].append(p)
            codigos_existentes.add(p['codigo'])
            agregados += 1

    with open(ARCHIVO_YAML, "w", encoding="utf-8") as f:
        yaml.dump(datos, f, allow_unicode=True, sort_keys=False)
    
    print(f"✅ Extracción completada. {agregados} nuevas partidas inyectadas al YAML.")

if __name__ == "__main__":
    print("=== EXTRACTOR MASIVO SERVIU v2 (MODO CAZADOR) ===")
    print("Escaneando Excels y buscando tablas...")
    partidas = extraer_partidas_excel()
    if partidas:
        actualizar_yaml(partidas)
    else:
        print("⚠️ Aún no se detectaron partidas. Los Excel pueden tener una estructura muy irregular.")
