import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.expanduser("~/DepaFix_Maestro/.env"))

def crear_supabase():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )

curso = {
    "codigo_sence": "1234567890",  # Reemplaza con el código real
    "nombre_curso": "Aplicar controles en el puesto de trabajo",
    "modalidad": "Presencial",
    "horas_cronologicas": 8,
    "numero_participantes": 15,
    "competencia": "Aplicar controles en el puesto de trabajo según normativa vigente",
    "aprendizajes_esperados": [
        "Identificar riesgos laborales",
        "Aplicar controles en el puesto de trabajo"
    ],
    "contenidos": [
        "Marco legal",
        "Identificación de riesgos",
        "Controles y EPP"
    ],
    "relatores": [
        {"nombre": "Nombre Relator", "rut": "12.345.678-9"}
    ],
    "costo_facilitador": 0,
    "costo_infraestructura": 0,
    "costo_materiales": 0,
    "costo_utilidades": 0,
    "total_curso": 0,
    "estado": "borrador"
}

crear_supabase().table("cursos_sence").upsert(
    curso,
    on_conflict="codigo_sence"
).execute()
print("✅ Curso cargado:", curso["codigo_sence"])
