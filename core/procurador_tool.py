"""
ProcuradorTool - Análisis de expedientes con Supabase SERVICE_ROLE
Usa db_manager centralizado y cumple reglas de oro.
"""
import time
from core.db_manager import db_manager

class ProcuradorTool:
    def __init__(self):
        self.supabase = db_manager.get_service_client()
        self.table = 'compliance_logs'
    
    def insertar_analisis(self, rol, etapa_procesal, riesgo_detectado, dictamen, metadata=None, max_retries=3):
        """Inserta un nuevo análisis con retry y telemetría en error_logs."""
        data = {
            "rol": rol,
            "etapa_procesal": etapa_procesal,
            "riesgo_detectado": riesgo_detectado,
            "dictamen": dictamen,
            "metadata": metadata or {}
        }
        for intento in range(max_retries):
            try:
                result = self.supabase.table(self.table).insert(data).execute()
                return result.data[0] if result.data else None
            except Exception as e:
                if intento < max_retries - 1:
                    time.sleep(0.5 * (intento + 1))
                    continue
                # Log a error_logs (telemetría)
                self._log_error('insertar_analisis', str(e), {'data': data})
                return None
    
    def obtener_analisis(self, limit=10):
        """Obtiene últimos análisis."""
        try:
            result = self.supabase.table(self.table).select('*').order('id', desc=True).limit(limit).execute()
            return result.data
        except Exception as e:
            self._log_error('obtener_analisis', str(e))
            return []
    
    def actualizar_dictamen(self, id_registro, nuevo_dictamen):
        """Actualiza dictamen de un registro."""
        try:
            result = self.supabase.table(self.table).update({"dictamen": nuevo_dictamen}).eq('id', id_registro).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self._log_error('actualizar_dictamen', str(e), {'id': id_registro, 'dictamen': nuevo_dictamen})
            return None
    
    def _log_error(self, funcion, mensaje, extra=None):
        """Registra error en error_logs (telemetría)."""
        try:
            error_data = {
                "modulo": "ProcuradorTool",
                "funcion": funcion,
                "mensaje": mensaje,
                "metadata": extra or {}
            }
            self.supabase.table('error_logs').insert(error_data).execute()
        except:
            pass  # Si falla, no podemos hacer nada

# Ejemplo de uso
if __name__ == "__main__":
    tool = ProcuradorTool()
    # Insertar caso real C-20129-2023 con dictamen "ACOGIDA"
    resultado = tool.insertar_analisis(
        rol="C-20129-2023",
        etapa_procesal="Sentencia firme",
        riesgo_detectado="Prescripción confirmada por Corte de Apelaciones",
        dictamen="ACOGIDA",
        metadata={
            "monto": 694132886,
            "fecha_sentencia": "2025-11-05",
            "corte": "4º Juzgado Civil de Santiago"
        }
    )
    if resultado:
        print(f"✅ Análisis insertado: ID {resultado['id']}")
    else:
        print("❌ Falló la inserción.")
    
    # Mostrar últimos análisis
    print("\n📋 Últimos 5 análisis:")
    for a in tool.obtener_analisis(5):
        print(f"  ID: {a['id']} | ROL: {a['rol']} | Dictamen: {a['dictamen']}")
