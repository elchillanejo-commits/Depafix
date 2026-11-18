import os
import subprocess
import unicodedata
import re
import sys

def limpiar_nombre(nombre):
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('utf-8').lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 en_analisis/nueva_ficha.py 'Nombre Completo'")
        sys.exit(1)
    
    nombre = sys.argv[1]
    archivo_base = limpiar_nombre(nombre)
    ruta_md = f"en_analisis/{archivo_base}.md"

    # Plantilla vacía (idéntica a la del Día 8)
    plantilla = f"""# Perfil: N° - {nombre}
Edad:
Rubro:
Cómo lo conocí:
Hace cuánto:
Última vez que hablamos:
Nivel_Tenis:
Red_de_contactos:
Personalidad:
Qué le importa:
Cómo decide:
Cómo me trata:
Su vida (familia, plata, problemas):
NO decirle:
Intuición mía:
"""
    # Si el archivo no existe, lo crea con la plantilla
    if not os.path.exists(ruta_md):
        with open(ruta_md, 'w', encoding='utf-8') as f:
            f.write(plantilla)
        print(f"✅ Ficha creada: {ruta_md}")
    else:
        print(f"📂 Abriendo ficha existente: {ruta_md}")

    # Abre nano automáticamente
    print("📝 Abriendo editor nano... (Guarda con Ctrl+O, Enter, y sal con Ctrl+X)")
    subprocess.run(["nano", ruta_md])

    print("\n✅ Ficha guardada. Ahora genera el análisis con la IA.")
    print("👉 Ejecuta: ~/gantt/bin/en-analyze " + archivo_base)

if __name__ == "__main__":
    main()
