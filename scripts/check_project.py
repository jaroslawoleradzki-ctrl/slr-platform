from app.core.config import load_project_config

config = load_project_config("projects/lean_energy/config.yaml")
print("Konfiguracja poprawna")
print("Projekt:", config.project.title)
print("Źródła:", ", ".join(config.sources))
