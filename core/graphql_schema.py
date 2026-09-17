import strawberry
from typing import List
@strawberry.type
class Query:
    @strawberry.field
    def presupuestos(self) -> List[str]: return ["P1", "P2"]
schema = strawberry.Schema(query=Query)
