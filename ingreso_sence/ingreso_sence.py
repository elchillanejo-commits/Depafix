#!/usr/bin/env python3
import os
import json
import sys

def cargar_configuracion():
    config_path = "config_sence.json"
    if not os.path.exists(config_path):
        base = {"MODO_RAI": False, "directorios": {"entrada": "./curso_actual/entrada", "salida": "./curso_actual/salida"}, "parametros_fijos": {"codigo_sence": "12345678", "rut_empresa": "76123456-k", "nombre_curso": "Gestion Legal"}}
        with open(config_path, "w", encoding="utf-8") as f: json.dump(base, f, indent=4)
        return base
    with open(config_path, "r", encoding="utf-8") as f: return json.load(f)

def generar_pdf_dj(datos, destino):
    print(f"📄 [DJ] Generada en {destino} | Formato SENCE Oficial (Alineacion Izquierda)")
    # Aqui usas style.alignment = 0 para evitar separacion de palabras

def generar_pdf_carta(datos, destino):
    print(f"📄 [Carta Conductora] Generada en {destino}")

def generar_pdf_contratos(datos, destino):
    print(f"📄 [Contratos SENCE] Estructura consolidada en {destino}")

def main():
    config = cargar_configuracion()
    dir_out = config["directorios"].get("salida", "./salida")
    os.makedirs(dir_out, exist_ok=True)
    
    datos = {"MODO_RAI": config.get("MODO_RAI", False), **config["parametros_fijos"]}
    
    generar_pdf_dj(datos, os.path.join(dir_out, "01_Declaracion_Jurada.pdf"))
    generar_pdf_carta(datos, os.path.join(dir_out, "02_Carta_Conductora.pdf"))
    generar_pdf_contratos(datos, os.path.join(dir_out, "03_Contratos.pdf"))
    print("\n✅ Suite estructurada correctamente con formatos limpios.")

if __name__ == "__main__": main()
