import json
from core.db_manager import DatabaseManager  # Ajusta el nombre según lo que encontraste

db = DatabaseManager()
client = db.get_service_client()

# Contenido del DOCX (copia el texto aquí o léelo de un archivo)
contenido = """
Perfecto. He integrado todos los elementos que me diste...
"""

client.table('documentos_estrategicos').insert({
    'titulo': 'Capacitación Pólizas de Garantía - Documento Estratégico',
    'tipo': 'CAPACITACION',
    'contenido': contenido,
    'metadata': {'version': '1.0', 'fecha': '2026-07-28'}
}).execute()

print("✅ Documento insertado")
