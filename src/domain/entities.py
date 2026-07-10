from __future__ import annotations
from uuid import UUID, uuid4
from .value_objects import Dinero, MetrosCuadrados, DuracionEstimada, EstadoObra

class Obra:
    """Raíz agregada del dominio de obras."""
    def __init__(
        self,
        id_obra: UUID,
        nombre: str,
        ubicacion: str,
        metros: MetrosCuadrados,
        estado: EstadoObra = EstadoObra.PENDIENTE
    ):
        self.id = id_obra
        self.nombre = nombre
        self.ubicacion = ubicacion
        self.metros = metros
        self.estado = estado
        self.prediccion: DuracionEstimada | None = None
        self._presupuesto: Dinero | None = None

    def asignar_prediccion(self, prediccion: DuracionEstimada):
        self.prediccion = prediccion

    def asignar_presupuesto(self, presupuesto: Dinero):
        if self.estado == EstadoObra.FINALIZADA:
            raise ValueError("No se puede modificar el presupuesto de una obra finalizada")
        self._presupuesto = presupuesto

    def finalizar(self):
        if self.prediccion is None:
            raise ValueError("No se puede finalizar sin una predicción")
        self.estado = EstadoObra.FINALIZADA
