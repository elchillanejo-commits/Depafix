import os, psycopg2, json
from uuid import UUID
from src.domain.ports import ObraRepositoryPort
from src.domain.entities import Obra
from src.domain.value_objects import MetrosCuadrados, DuracionEstimada, Confianza, EstadoObra

class PostgresObraRepository(ObraRepositoryPort):
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST","localhost"),
            user=os.getenv("DB_USER","depafix"),
            password=os.getenv("DB_PASS"),  # sin fallback: credencial hardcodeada removida (auditoria 2026-07-16, repo publico)
            dbname=os.getenv("DB_NAME","depafix")
        )
    def guardar(self, obra: Obra):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO obras.obras_ddd (id, descripcion, ubicacion, metros, estado, prediccion_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET estado=EXCLUDED.estado, prediccion_json=EXCLUDED.prediccion_json
        """, (str(obra.id), obra.nombre, obra.ubicacion, obra.metros.valor, obra.estado.value,
              obra.prediccion.model_dump_json() if obra.prediccion else None))
        self.conn.commit()
        cur.close()
    def buscar_por_id(self, id_obra: str) -> Obra | None:
        cur = self.conn.cursor()
        cur.execute("SELECT id, descripcion, ubicacion, metros, estado, prediccion_json FROM obras.obras_ddd WHERE id=%s", (id_obra,))
        row = cur.fetchone()
        cur.close()
        if not row: return None
        obra = Obra(UUID(row[0]), row[1], row[2], MetrosCuadrados(valor=row[3]), EstadoObra(row[4]))
        if row[5]: obra.asignar_prediccion(DuracionEstimada.model_validate_json(row[5]))
        return obra
