import sys
import os
import unicodedata
import re
import subprocess

def limpiar_nombre(nombre):
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('utf-8').lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')

if len(sys.argv) < 2:
    print("Uso: python3 en_analisis/pegar_ficha.py 'N°\tNombre\tEdad\tRubro...'")
    sys.exit(1)

# Recibimos la línea cruda que copiaste de tu Excel
linea_cruda = sys.argv[1]
partes = linea_cruda.split('\t')

if len(partes) < 35:
    print("Error: La línea no tiene el formato correcto (debe tener los datos separados por tabulación).")
    sys.exit(1)

num = partes[0].strip()
nombre = partes[1].strip()
edad = partes[2].strip()
rubro = partes[3].strip()
conozco_desde = partes[4].strip()
ultima_charla = partes[5].strip()
frecuencia = partes[6].strip()
cercania = partes[7].strip()
confianza = partes[8].strip()
base_relacion = partes[9].strip()
nivel_tenis = partes[10].strip()
red = partes[11].strip()
estado_civil = partes[12].strip()
hijos = partes[13].strip()
vive_en = partes[14].strip()
economia = partes[15].strip()
problemas = partes[16].strip()
logros = partes[17].strip()
le_importa = partes[18].strip()
le_molesta = partes[19].strip()
como_decide = partes[20].strip()
riesgo = partes[21].strip()
conoce_gente = partes[22].strip()
circulos = partes[23].strip()
red_util = partes[24].strip()
presenta_gente = partes[25].strip()
le_pedi = partes[26].strip()
me_pidio = partes[27].strip()
pendientes = partes[28].strip()
eneatipo = partes[29].strip()
arquetipo = partes[30].strip()
porque = partes[31].strip()
no_decir = partes[32].strip()
si_decir = partes[33].strip()
speech = partes[34].strip()

# Formateamos el texto para el editor nano
contenido = f"""# Perfil: N° {num} - {nombre}
Edad: {edad}
Rubro: {rubro}
Cómo lo conocí: {partes[9] if len(partes)>9 else ''}
Hace cuánto: {conozco_desde}
Última vez que hablamos: {ultima_charla}
Nivel_Tenis: {nivel_tenis}
Red_de_contactos: {red}
Personalidad: {porque}
Qué le importa: {le_importa}
Cómo decide: {como_decide}
Cómo me trata: {base_relacion}
Su vida (familia, plata, problemas): {problemas} / {logros}
NO decirle: {no_decir}
Intuición mía: {si_decir}

=========================================
ANÁLISIS PREVIO (SI YA LO TIENES):
Eneatipo: {eneatipo}
Arquetipo: {arquetipo}
Speech original: {speech}
"""

archivo_base = limpiar_nombre(nombre)
ruta_md = f"en_analisis/{archivo_base}.md"

# Escribimos el archivo temporal
with open(ruta_md, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"✅ Archivo generado con los datos de {nombre}.")
print("📝 Abriendo editor nano... (Guarda con Ctrl+O, Enter, y sal con Ctrl+X)")
subprocess.run(["nano", ruta_md])

print(f"\n✅ Ficha guardada en: {ruta_md}")
