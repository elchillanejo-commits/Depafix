import os
import webbrowser
import yaml

def generar_presupuesto_html(codigo_partida, comuna, magnitud):
    # 1. Leer el catálogo base SERVIU
    with open("serviu_precios.yml", "r", encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    
    # 2. Extraer la partida exacta
    partidas = datos.get("partidas", [])
    partida = next((p for p in partidas if p["codigo"] == codigo_partida), None)
    
    if not partida:
        print(f"❌ Error: Código {codigo_partida} no existe en la base SERVIU.")
        return

    nombre = partida["nombre"]
    unidad = partida["unidad"]
    precio_unitario = partida["precio_unitario"]
    
    # 3. Cálculos matemáticos limpios
    total_neto = magnitud * precio_unitario
    iva = int(total_neto * 0.19)
    total_final = total_neto + iva
    
    # 4. Inyectar datos reales en el Template HTML
    with open("presupuesto_template.html", "r", encoding="utf-8") as f:
        template = f.read()
        
    html = template.replace("{comuna}", comuna)\
                   .replace("{partida}", nombre)\
                   .replace("{magnitud}", f"{magnitud} {unidad}")\
                   .replace("{precio_unitario}", f"{precio_unitario:,}")\
                   .replace("{total_neto}", f"{total_neto:,}")\
                   .replace("{iva}", f"{iva:,}")\
                   .replace("{total_final}", f"{total_final:,}")
                   
    # 5. Guardar output modular y abrir
    output_file = f"presupuesto_{codigo_partida.lower()}.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
        
    print(f"✅ Cotización blindada: {output_file} (Valor SERVIU aplicado: ${precio_unitario:,})")
    webbrowser.open(f"file://{os.path.abspath(output_file)}")

if __name__ == "__main__":
    print("=== MOTOR COTIZADOR DEPAFIX (MODO SERVIU) ===")
    generar_presupuesto_html("CER-001", "Ñuñoa", 50)
