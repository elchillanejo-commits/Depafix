from fastapi import APIRouter
from uuid import uuid4
from src.domain.entities import Obra
from src.domain.value_objects import MetrosCuadrados
from src.application.prediction_service import ObraPredictionService
from src.infrastructure.models.prediction_engine import SimplePredictionEngine
from src.infrastructure.persistence.postgres_repository import PostgresObraRepository

router = APIRouter(prefix="/obras", tags=["Obras DDD"])

@router.post("/predecir-duracion")
def predecir_duracion(nombre: str, ubicacion: str, metros: float):
    engine = SimplePredictionEngine()
    repo = PostgresObraRepository()
    service = ObraPredictionService(engine, repo)
    
    area = MetrosCuadrados(valor=metros)
    obra = Obra(id_obra=uuid4(), nombre=nombre, ubicacion=ubicacion, metros=area)
    obra = service.predecir_y_guardar(obra)
    
    return {
        "id": str(obra.id),
        "prediccion_dias": obra.prediccion.dias,
        "confianza": obra.prediccion.confianza.valor,
        "estado": obra.estado
    }
