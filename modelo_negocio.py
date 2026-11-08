import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno (por si acaso, aunque no es necesario para la simulación pura)
load_dotenv()

# ==========================================
# PARÁMETROS DEL MODELO DE NEGOCIO (AJUSTABLES)
# ==========================================
TIPO_CAMBIO_USD_CLP = 950.0
COSTO_FIJO_USD = 5.0 + 3.0 # Railway + API Kimi
COSTO_FIJO_CLP = COSTO_FIJO_USD * TIPO_CAMBIO_USD_CLP

# Precios de planes (en CLP)
PLAN_BASICO_CLP = 9990.0
PLAN_PRO_CLP = 29990.0

# Proyección de usuarios (mes 1 a 6)
# Formato: (clientes_basico, clientes_pro)
PROYECCION_USUARIOS = [
    (5, 0),    # Mes 1
    (10, 2),   # Mes 2
    (12, 3),   # Mes 3
    (15, 4),   # Mes 4
    (18, 5),   # Mes 5
    (22, 6)    # Mes 6
]

# ==========================================
# LÓGICA DE CÁLCULO
# ==========================================
def calcular_modelo():
    print("=" * 60)
    print(" MODELO DE NEGOCIO: COTIZADOR DEPAFIX (SaaS)")
    print("=" * 60)
    print(f" Costo Fijo Mensual: ${COSTO_FIJO_CLP:,.0f} CLP (${COSTO_FIJO_USD:.2f} USD)")
    print(f" Precio Plan Básico: ${PLAN_BASICO_CLP:,.0f} CLP")
    print(f" Precio Plan Pro:    ${PLAN_PRO_CLP:,.0f} CLP")
    print("-" * 60)
    print(f" {'Mes':<5} | {'Básicos':<8} | {'Pro':<8} | {'Ingreso Total (CLP)':<20} | {'Utilidad (CLP)':<15}")
    print("-" * 60)

    for i, (basicos, pro) in enumerate(PROYECCION_USUARIOS, start=1):
        ingreso_basicos = basicos * PLAN_BASICO_CLP
        ingreso_pro = pro * PLAN_PRO_CLP
        ingreso_total = ingreso_basicos + ingreso_pro
        utilidad = ingreso_total - COSTO_FIJO_CLP

        print(f" {i:<5} | {basicos:<8} | {pro:<8} | ${ingreso_total:>15,.0f} | ${utilidad:>12,.0f}")

    print("=" * 60)
    print(" ANÁLISIS:")
    break_even_meses = 0
    for i, (basicos, pro) in enumerate(PROYECCION_USUARIOS, start=1):
        ingreso = (basicos * PLAN_BASICO_CLP) + (pro * PLAN_PRO_CLP)
        if ingreso >= COSTO_FIJO_CLP:
            break_even_meses = i
            break
    
    if break_even_meses > 0:
        print(f" ✅ Break-even alcanzado en el Mes {break_even_meses}.")
    else:
        print(" ❌ No se alcanza el break-even en el período proyectado.")

    print(f" 📈 Crecimiento de usuarios: {PROYECCION_USUARIOS[0]} a {PROYECCION_USUARIOS[-1]} (Mes 1 a Mes 6)")
    print("=" * 60)

if __name__ == "__main__":
    calcular_modelo()
