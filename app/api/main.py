from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    deduplication,
    extraction,
    full_text_screening,
    normalization,
    projects,
    quality_assessment,
    screening,
    search_strategy,
)
from app.core.config import load_project_config
from app.repositories.project_repository import default_project_repository


def _application_version() -> str:
    return (Path(__file__).parents[2] / "VERSION").read_text(encoding="utf-8").strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    default_project_repository()
    yield


app = FastAPI(title="SLR Platform", version=_application_version(), lifespan=lifespan)



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
app.include_router(full_text_screening.router)
app.include_router(quality_assessment.router)
app.include_router(extraction.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/version")
def api_version():
    return {"name": "SLR Platform", "version": _application_version()}


@app.get("/projects/lean_energy")
def project():
    return load_project_config("projects/lean_energy/config.yaml").model_dump()


_FRONTEND_DIST = Path(__file__).parents[2] / "frontend" / "dist"

if (_FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")


@app.get("/")
def root():
    index_file = _FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"name": "SLR Platform", "version": _application_version()}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "v1/")):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    file_path = _FRONTEND_DIST / full_path
    if file_path.is_file():
        return FileResponse(file_path)

    index_file = _FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    return JSONResponse(status_code=404, content={"detail": "Not Found"})

