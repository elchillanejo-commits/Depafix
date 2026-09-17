#!/usr/bin/env python3
"""
Exporta los documentos estratégicos de Supabase a archivos de texto locales.
Ejecutar con el entorno virtual activado.
"""

import os
import json
import re
from pathlib import Path
from core.db_manager import DatabaseManager

def sanitizar_nombre(titulo):
    """Convierte el título en un nombre de archivo válido."""
    # Reemplazar caracteres no permitidos por guión bajo
    nombre = re.sub(r'[^\w\s-]', '', titulo)
    nombre = re.sub(r'[-\s]+', '_', nombre)
    return nombre[:50]  # Limitar longitud

def main():
    # Verificar que el entorno virtual esté activo
    if not os.getenv('VIRTUAL_ENV'):
        print("⚠️  No parece que el entorno virtual esté activo.")
        print("Ejecuta: source .venv/bin/activate")
        return 1

    # Crear carpeta de destino
    output_dir = Path('data/documentos_estrategicos')
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Carpeta de destino: {output_dir.absolute()}")

    # Conectar a Supabase
    try:
        db = DatabaseManager()
        client = db.get_service_client()
    except Exception as e:
        print(f"❌ Error al conectar a Supabase: {e}")
        return 1

    # Obtener todos los documentos
    try:
        result = client.table('documentos_estrategicos').select('*').execute()
        documentos = result.data
    except Exception as e:
        print(f"❌ Error al consultar la tabla: {e}")
        return 1

    if not documentos:
        print("ℹ️  No hay documentos en la tabla.")
        return 0

    print(f"📄 Se encontraron {len(documentos)} documento(s).")

    # Guardar cada documento
    metadatos = []
    for doc in documentos:
        titulo = doc.get('titulo', 'Sin_titulo')
        contenido = doc.get('contenido', '')
        doc_id = doc.get('id', 'desconocido')

        # Sanitizar nombre de archivo
        nombre_base = sanitizar_nombre(titulo)
        nombre_archivo = f"{doc_id:03d}_{nombre_base}.txt"
        ruta = output_dir / nombre_archivo

        # Escribir contenido
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(f"Título: {titulo}\n")
            f.write(f"ID: {doc_id}\n")
            f.write(f"Tipo: {doc.get('tipo', 'N/A')}\n")
            f.write(f"Fecha: {doc.get('created_at', 'N/A')}\n")
            f.write("-" * 80 + "\n\n")
            f.write(contenido)

        print(f"✅ Guardado: {ruta.name}")

        # Guardar metadatos
        metadatos.append({
            'id': doc_id,
            'titulo': titulo,
            'tipo': doc.get('tipo'),
            'created_at': doc.get('created_at'),
            'archivo': str(ruta)
        })

    # Guardar índice de metadatos
    index_path = output_dir / 'index.json'
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(metadatos, f, indent=2, ensure_ascii=False)

    print(f"📋 Índice guardado en: {index_path}")
    print("✅ Exportación completada.")
    return 0

if __name__ == '__main__':
    exit(main())
