import os
import json
import glob
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def construir_contexto_maestro():
    local_dir = "data/knowledge_base"
    output_file = "data/contexto_maestro.txt"
    
    if not os.path.exists(local_dir):
        log.error(f"No existe la carpeta {local_dir}")
        return

    archivos = glob.glob(os.path.join(local_dir, "*.json"))
    if not archivos:
        log.warning("No hay archivos JSON en la base de conocimiento.")
        return

    log.info(f"🧠 Construyendo Cerebro Local con {len(archivos)} videos...")
    
    contexto_total = ""
    for archivo in archivos:
        with open(archivo, "r", encoding="utf-8") as f:
            data = json.load(f)
            contexto_total += f"\n\n--- CONOCIMIENTO: {data['titulo']} ---\n"
            contexto_total += data['contenido']

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(contexto_total)

    tamanio_kb = os.path.getsize(output_file) / 1024
    log.info(f"✅ Contexto maestro generado en: {output_file}")
    log.info(f"📦 Peso total: {tamanio_kb:.2f} KB")
    log.info("💡 Listo para inyectar en el prompt del LLM (OpenAI/Kimi/Claude).")

if __name__ == "__main__":
    construir_contexto_maestro()
