#!/usr/bin/env python3
import os, sys, json, time, logging
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import jsonschema
from jsonschema import validate

try:
    from core.engine import predict
except ImportError:
    def predict(data): return {"error": "engine no disponible"}

try:
    from core.db_manager import db
except ImportError:
    class MockDB:
        def execute(self, sql, params=None): return None
    db = MockDB()

try:
    import core.circuit_state as circuit_state
    circuit_state.reset_all()
    print("✅ Circuit State inicializado")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("depafix-api")
app = FastAPI(title="DepaFix API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

try:
    with open("schema.json") as f: SCHEMA = json.load(f)
except:
    SCHEMA = {"type": "object", "properties": {"departamento": {"type": "string"}, "items": {"type": "array"}}, "required": ["departamento", "items"]}

@app.get("/health")
async def health(): return {"status": "ok"}

@app.post("/predict")
async def predict_endpoint(request: Request):
    try:
        data = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON")
    try:
        validate(instance=data, schema=SCHEMA)
    except jsonschema.ValidationError as e:
        raise HTTPException(422, detail=str(e))
    try:
        return JSONResponse(predict(data))
    except Exception as e:
        logger.exception("Predicción falló")
        raise HTTPException(500, detail="Error en predicción")

@app.get("/status")
async def system_status():
    db_status = {"connected": False, "response_time_ms": None, "record_count": None}
    try:
        start = time.perf_counter()
        result = db.execute("SELECT COUNT(*) FROM \"presupuestos\"")
        count = result.scalar() if result else 0
        db_status["connected"] = True
        db_status["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
        db_status["record_count"] = count
    except Exception as e:
        db_status["error"] = str(e)

    ml_status = {"exists": False}
    model_path = Path(__file__).resolve().parent / "models" / "depafix_model_v1.pkl"
    if model_path.exists():
        ml_status["exists"] = True
        ml_status["last_modified"] = datetime.fromtimestamp(os.path.getmtime(model_path)).isoformat()
        import re
        match = re.search(r"v(\d+)", model_path.name)
        ml_status["version"] = f"v{match.group(1)}" if match else "unknown"

    try:
        import core.circuit_state as circuit_state
        cb_state = circuit_state.get_circuit_state()
        failures = circuit_state.get_failures()
    except ImportError:
        cb_state = "unknown"
        failures = {}

    return {
        "database": db_status,
        "ml_model": ml_status,
        "circuit_breaker": {"state": cb_state, "failures": failures},
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
