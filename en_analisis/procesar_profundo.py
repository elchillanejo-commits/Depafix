import pandas as pd

def clasificar_por_reglas(texto):
    texto = str(texto).lower()
    if 'tímid' in texto or 'introvertid' in texto: 
        return '5w6', 'Descartes'
    if 'frontal' in texto or 'rudo' in texto or 'competitivo' in texto: 
        return '8w9', 'Sun Tzu'
    if 'sensible' in texto or 'servicial' in texto: 
        return '2w3', 'San Francisco'
    if 'pillo' in texto or 'plata' in texto or 'mujeres' in texto: 
        return '3w4', 'Maquiavelo'
    if 'leal' in texto or 'prudente' in texto: 
        return '6w5', 'Séneca'
    if 'extrovertido' in texto or 'loca' in texto or 'escenarios' in texto: 
        return '7w8', 'Epicuro'
    if 'ego' in texto or 'imagen' in texto: 
        return '3w2', 'Maquiavelo'
    if 'paz' in texto or 'tranquilo' in texto: 
        return '9w1', 'Lao Tsé'
    return 'Por clasificar', 'Desconocido'

print("Leyendo Excel...")
df = pd.read_excel('Lista 300 (4).xlsx', sheet_name='Prospectos')
df = df.fillna('')

faltantes = df[df['Eneatipo'] == '?']
print(f"Procesando {len(faltantes)} prospectos que tienen '?'...")

resultados = []
for index, row in faltantes.iterrows():
    nombre = row['Nombre']
    info = str(row['Info_clave'])
    speech = str(row['Speech_clave'])
    
    eneatipo, arquetipo = clasificar_por_reglas(info + " " + speech)
    
    resultados.append({'N°': row['N°'], 'Nombre': nombre, 'Eneatipo': eneatipo, 'Arquetipo': arquetipo})
    print(f"✅ {nombre} -> {eneatipo} / {arquetipo}")

pd.DataFrame(resultados).to_csv('en_analisis/resultados_finales.csv', index=False)
print("¡Listo! Archivo generado en en_analisis/resultados_finales.csv")
