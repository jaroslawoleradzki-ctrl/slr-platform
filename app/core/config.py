from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

class ProjectInfo(BaseModel):
    id: str
    title: str
    protocol_version: str | None = None

class ProjectConfig(BaseModel):
    project: ProjectInfo
    sources: dict[str, Any] = Field(default_factory=dict)
    search: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    deduplication: dict[str, Any] = Field(default_factory=dict)
    export: dict[str, Any] = Field(default_factory=dict)
    logging: dict[str, Any] = Field(default_factory=dict)
    ai: dict[str, Any] = Field(default_factory=dict)

def load_project_config(path: str | Path) -> ProjectConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("Nieprawidłowy plik YAML")
    return ProjectConfig.model_validate(data)
