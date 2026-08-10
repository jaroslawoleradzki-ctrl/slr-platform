from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    deduplication,
    normalization,
    projects,
    screening,
    search_strategy,
)
from app.core.config import load_project_config


def _application_version() -> str:
    return (Path(__file__).parents[2] / "VERSION").read_text(encoding="utf-8").strip()


app = FastAPI(title="SLR Platform", version=_application_version())

# Configure CORS for local development
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(deduplication.router)
app.include_router(search_strategy.router)
app.include_router(normalization.router)
app.include_router(screening.router)


@app.get("/")
def root():
    return {"name": "SLR Platform", "version": _application_version()}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/projects/lean_energy")
def project():
    return load_project_config("projects/lean_energy/config.yaml").model_dump()
