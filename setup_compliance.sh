#!/bin/bash
# setup_compliance.sh – Configura compliance_logs y variables, luego prueba el parser

echo "🔧 Configurando compliance_logs y variables de entorno..."

# 1. Agregar variables a .env si no existen
if ! grep -q "MIGRATION_FIRM_ID" .env 2>/dev/null; then
    echo "MIGRATION_FIRM_ID=f47ac10b-58cc-4372-a567-0e02b2c3d479" >> .env
    echo "MIGRATION_USER_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890" >> .env
    echo "   ✅ Variables agregadas a .env"
else
    echo "   ℹ️  Variables ya existen en .env"
fi

# 2. Crear tabla compliance_logs en Supabase (si no existe)
python3 -c "
from core.db_manager import DatabaseManager
sp = DatabaseManager.get_client()

# Intentar crear la tabla insertando un registro ficticio con los campos requeridos
try:
    # Si la tabla no existe, Supabase devolverá error; lo ignoramos y la creamos con SQL directo
    sp.table('compliance_logs').select('log_id').limit(1).execute()
    print('ℹ️  La tabla compliance_logs ya existe.')
except Exception as e:
    if 'PGRST205' in str(e):
        print('📦 Creando tabla compliance_logs...')
        # Usamos SQL directo a través del cliente (requiere permisos de service_role)
        sql = '''
        CREATE TABLE IF NOT EXISTS compliance_logs (
            log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            record_id UUID REFERENCES records(record_id),
            firm_id UUID REFERENCES law_firms(firm_id),
            document_hash TEXT NOT NULL,
            analysis_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            verdict TEXT NOT NULL CHECK (verdict IN ('APROBADO','RECHAZADO','NEGOCIAR','PENDIENTE')),
            risk_score NUMERIC(3,2) NOT NULL DEFAULT 0,
            critical_risks JSONB NOT NULL DEFAULT '[]'::jsonb,
            safeguard_clauses JSONB NOT NULL DEFAULT '[]'::jsonb,
            raw_analysis JSONB,
            rol VARCHAR(20),
            tribunal TEXT,
            etapa_procesal TEXT,
            litigantes JSONB DEFAULT '[]'::jsonb,
            proximo_plazo DATE,
            idempotency_key TEXT UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        '''
        sp.rpc('exec_sql', {'query': sql}).execute()
        print('✅ Tabla compliance_logs creada.')
    else:
        raise

# Insertar estudio jurídico y miembro si no existen
from dotenv import load_dotenv
import os
load_dotenv()
firm_id = os.getenv('MIGRATION_FIRM_ID')
user_id = os.getenv('MIGRATION_USER_ID')
if firm_id and user_id:
    try:
        sp.table('law_firms').insert({'firm_id': firm_id, 'name': 'Estudio Histórico'}).execute()
    except: pass
    try:
        sp.table('firm_members').insert({'firm_id': firm_id, 'user_id': user_id, 'role': 'titular'}).execute()
    except: pass
print('✅ Configuración completada.')
"

# 3. Cargar variables y ejecutar parser
source .env
python3 core/procurador_tool.py parse core/demanda_cge.pdf
