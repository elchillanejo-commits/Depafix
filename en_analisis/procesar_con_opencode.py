import sys
import os
import subprocess

if len(sys.argv) < 2:
    print("Uso: python3 en_analisis/procesar_con_opencode.py <nombre_archivo_sin_extension>")
    sys.exit(1)

nombre_base = sys.argv[1]
ruta_md = f"en_analisis/{nombre_base}.md"

if not os.path.exists(ruta_md):
    print(f"Error: No se encuentra el archivo {ruta_md}")
    sys.exit(1)

print(f"🧠 Enviando {nombre_base} a OpenCode (DeepSeek) para análisis...")

# Comando de OpenCode que lee, analiza y guarda
comando = f'opencode run "Lee el archivo {ruta_md} y analízalo. Devuélveme el Eneatipo, Arquetipo, Diagnóstico y un Speech de WhatsApp personalizado. Al final, agrega el análisis al final del mismo archivo." --agent build'

try:
    # Ejecutamos el comando y mostramos la salida en vivo
    subprocess.run(comando, shell=True, check=True)
    print(f"\n✅ Análisis completado y guardado en: {ruta_md}")
except subprocess.CalledProcessError as e:
    print(f"\n❌ Error al ejecutar OpenCode: {e}")
