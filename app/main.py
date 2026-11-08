from fastapi import FastAPI
from app.routes import auth, cotizaciones

app = FastAPI(
    title="DepaFix SaaS API", 
    description="API para el Motor de Cotizaciones y Gestión de Usuarios",
    version="1.0.0"
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])
app.include_router(cotizaciones.router, prefix="/api/v1/cotizaciones", tags=["Cotizaciones"])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API de Cotizaciones DepaFix funcionando"}
