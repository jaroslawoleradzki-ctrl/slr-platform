from app.modules.normalize.service import normalize_doi, normalize_title

def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"

def test_normalize_title():
    assert normalize_title("Lean: Energy!") == "lean energy"
