import requests
from config.settings import BASE_DIR

def verificar_estado():
    print("[CENTINELA] Iniciando auditoría de red...")
    # Verificar acceso a la URL de Supabase (sin exponer claves)
    url = "https://gylyzcjkswltwpouktbi.supabase.co/rest/v1/presupuestos"
    try:
        # Usamos tu anon_key (asegúrate de tenerla en el .env)
        response = requests.get(url, headers={"apikey": "tu_anon_key_aqui"})
        if response.status_code == 200:
            print("[OK] Sistema en línea: Datos de precios_serviu accesibles.")
        else:
            print(f"[ALERTA] Código de estado: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Conexión caída: {e}")

if __name__ == "__main__":
    verificar_estado()
