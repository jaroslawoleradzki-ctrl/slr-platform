from fastapi import FastAPI
from app.core.config import load_project_config

app = FastAPI(title="SLR Platform", version="0.1.0")

@app.get("/")
def root():
    return {"name": "SLR Platform", "version": "0.1.0"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/projects/lean_energy")
def project():
    return load_project_config(
        "projects/lean_energy/config.yaml"
    ).model_dump()
