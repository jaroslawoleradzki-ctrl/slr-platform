from pathlib import Path

def import_google_scholar(path: str | Path):
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    raise NotImplementedError(
        "Import RIS/BibTeX/CSV z Google Scholar lub Publish or Perish "
        "będzie wdrożony w następnym etapie."
    )
