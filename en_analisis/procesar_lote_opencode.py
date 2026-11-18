import os
import subprocess
import time

# Lista de los 50 archivos generados (puedes agregar/quitar según necesites)
archivos = [
    "alejandro_bastias", "alejandro_ortiz_stade", "alejandro_serrano", "bernardo_pachi",
    "carolina_madrid_stade", "carolina_palma", "cassarino", "christian_letelier",
    "cristobal_cifuentes_stade", "diego_aburto", "edgar_malonnek", "erasmo",
    "ernesto_diaz", "esposa_ronny_maguire", "esteban_panes", "fabian_abarca",
    "hernan_sepulveda_stade", "jorge_stecher", "jose_luis_olavarri", "mandela",
    "marcelo_cerda", "maria_teresa_astorga", "miguel_llao_stade", "pablo_chavez",
    "pablo_fredes", "pablo_vera", "pamela_hoffman", "papa_rodrigo_lezana",
    "patricio_llanos", "paulina_lamatta", "pedro_natacion", "pessotti",
    "pia_berrios", "rafa_bustos", "rene_moya", "rodrigo_izurieta_stade",
    "rodrigo_lezana", "ronny_maguire", "salcedo", "santiago_fernandez",
    "sebastian_ugarte", "sergio_arancibia", "sergio_cabezas", "sherly_ravello",
    "soledad_maureira", "stefano_munoz", "vergara", "victor_bertrand",
    "victor_rios", "victor_silva"
]

print(f"🚀 Iniciando procesamiento automático de {len(archivos)} fichas...")
print("Esto puede tardar varios minutos. No cierres la terminal.\n")

for i, archivo in enumerate(archivos, 1):
    ruta_md = f"en_analisis/{archivo}.md"
    
    if not os.path.exists(ruta_md):
        print(f"⚠️ Saltando {archivo} (archivo no encontrado)")
        continue
        
    print(f"[{i}/{len(archivos)}] Procesando: {archivo}...")
    
    # Ejecutamos el comando de OpenCode para este archivo
    # Usamos --agent build que es el que tiene todos los permisos
    comando = f'opencode run "Lee el archivo {ruta_md} y analízalo. Devuélveme el Eneatipo, Arquetipo, Diagnóstico y un Speech de WhatsApp personalizado. Al final, agrega el análisis al final del mismo archivo." --agent build'
    
    try:
        # check=True hace que si falla, se detenga. En este caso, preferimos que siga.
        subprocess.run(comando, shell=True, check=False)
        print(f"✅ Completado: {archivo}\n")
    except Exception as e:
        print(f"❌ Error en {archivo}: {e}\n")
    
    # Pausa de 2 segundos para no saturar
    time.sleep(2)

print("🎉 ¡Proceso por lotes finalizado!")
