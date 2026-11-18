import unicodedata
import re

def limpiar_nombre(nombre):
    s = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('utf-8').lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')

print("=========================================")
print(" 🤖 ASISTENTE DE FICHAS DEPAFIX 🤖")
print("=========================================")
print("Presiona ENTER para saltar un campo si no lo sabes.\n")

nombre = input("1. Nombre completo (ej. Diego Cabrera): ").strip()
if not nombre:
    print("El nombre es obligatorio. Saliendo...")
    exit()

num = input("2. Número de prospecto (ej. 45): ").strip()
rubro = input("3. Rubro (ej. Abogado, Construcción, Tenis): ").strip()
vinculo = input("4. Cómo lo conocí (ej. Tenis, Stade, Padel): ").strip()
hace_cuanto = input("5. Hace cuánto lo conozco: ").strip()
ultima_vez = input("6. Última vez que hablamos: ").strip()
nivel_tenis = input("7. Nivel de tenis (ej. Yo gano, Él gana, Parejo): ").strip()
red = input("8. Red de contactos (Baja, Media, Alta): ").strip()
personalidad = input("9. Personalidad (ej. Tímido, inteligente, extrovertido): ").strip()
le_importa = input("10. Qué le importa (ej. Familia, plata, tenis): ").strip()
como_decide = input("11. Cómo decide (ej. Lógico, impulsivo, cauto): ").strip()
como_me_trata = input("12. Cómo me trata: ").strip()
vida = input("13. Su vida (familia, plata, problemas): ").strip()
no_decir = input("14. NO decirle (ej. Que es malo, presión): ").strip()
intuicion = input("15. Mi intuición (ej. Podría darme contactos para OTEC): ").strip()

archivo_base = limpiar_nombre(nombre)
ruta_md = f"en_analisis/{archivo_base}.md"

contenido = f"""# Perfil: N° {num} - {nombre}
Edad: 
Rubro: {rubro}
Cómo lo conocí: {vinculo}
Hace cuánto: {hace_cuanto}
Última vez que hablamos: {ultima_vez}
Nivel_Tenis: {nivel_tenis}
Red_de_contactos: {red}
Personalidad: {personalidad}
Qué le importa: {le_importa}
Cómo decide: {como_decide}
Cómo me trata: {como_me_trata}
Su vida (familia, plata, problemas): {vida}
NO decirle: {no_decir}
Intuición mía: {intuicion}
"""

with open(ruta_md, "w", encoding="utf-8") as f:
    f.write(contenido)

print("\n=========================================")
print(f"✅ Ficha guardada en: {ruta_md}")
print("=========================================")
print("\nCopia este texto y pégalo en Gemini para que haga el análisis:\n")
print("-" * 40)
print(contenido)
print("-" * 40)
print("\n💡 Tip: También puedes abrir el archivo con 'nano' si quieres editarlo.")
