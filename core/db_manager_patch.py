# Parche para añadir get_service_client a DatabaseManager
from core.db_manager import DatabaseManager

# Monkey-patch el método faltante
if not hasattr(DatabaseManager, 'get_service_client'):
    @classmethod
    def get_service_client(cls):
        return cls.get_client()
    DatabaseManager.get_service_client = get_service_client
    print("✅ Parche: get_service_client añadido a DatabaseManager")
