from fastapi import FastAPI, Depends
from core.middleware.auth import verify_auth
app = FastAPI()
@app.get("/health")
def health(): return {"status": "ok"}
@app.get("/nav")
def nav(user=Depends(verify_auth)): return {"message": "dashboard"}

@app.post("/hermes/run")
def run_hermes():
    return {"status": "scraping_in_progress"}
