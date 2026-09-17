from core.db_manager import DatabaseManager  # Ajusta el nombre

db = DatabaseManager()
client = db.get_service_client()

client.table('compliance_logs').insert({
    'rol': 'CAPACITACION-POLIZAS-2026',
    'etapa_procesal': 'Documento Estratégico',
    'dictamen': 'INFORMATIVO',
    'riesgo_detectado': 'Material sobre defensa de pólizas de garantía',
    'metadata': {
        'contenido': '...',  # Resumen del DOCX
        'tipo': 'FODA/ESTRATEGIA',
        'fecha': '2026-07-28'
    }
}).execute()

print("✅ Registro insertado en compliance_logs")
