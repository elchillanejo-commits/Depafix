
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import psycopg2, os

DB = dict(host=os.getenv("DB_HOST","localhost"), user=os.getenv("DB_USER","depafix"),
          password=os.getenv("DB_PASS"), dbname=os.getenv("DB_NAME","depafix"))
          # DB_PASS sin fallback: credencial hardcodeada removida (auditoria 2026-07-16, repo publico)

@strawberry.type
class Presupuesto: id: int; descripcion: str; total: float
@strawberry.type
class Proveedor: id: int; razon_social: str; email: str
@strawberry.type
class InventarioCritico: total: int
@strawberry.type
class PresupuestosResumen: total: int; activos: int

def query_db(sql):
    conn = psycopg2.connect(**DB); cur = conn.cursor()
    cur.execute(sql); rows = cur.fetchall(); cur.close(); conn.close()
    return rows

@strawberry.type
class Query:
    @strawberry.field
    def presupuestos(self) -> PresupuestosResumen:
        rows = query_db("SELECT COUNT(*), COUNT(*) FILTER(WHERE estado='activo') FROM obras.presupuestos")
        return PresupuestosResumen(total=rows[0][0], activos=rows[0][1])
    @strawberry.field
    def inventario_critico(self) -> InventarioCritico:
        rows = query_db("SELECT COUNT(*) FROM obras.inventario_materiales WHERE stock_actual <= stock_minimo")
        return InventarioCritico(total=rows[0][0])
    @strawberry.field
    def proveedores(self) -> list[Proveedor]:
        rows = query_db("SELECT id, razon_social, email FROM compras.proveedores LIMIT 50")
        return [Proveedor(id=r[0], razon_social=r[1], email=r[2]) for r in rows]

schema = strawberry.Schema(query=Query)
