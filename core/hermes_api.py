from fastapi import FastAPI
app = FastAPI()
@app.post("/hermes/run")
def run_hermes():
    return {"status": "scraping_in_progress"}
