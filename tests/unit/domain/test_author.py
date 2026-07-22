from app.domain.author import Affiliation, Author


def test_author_contains_affiliations() -> None:
    affiliation = Affiliation(name=" Poznan University of Economics ", country_code="pl")
    author = Author(display_name=" Jaroslaw Oleradzki ", affiliations=[affiliation])

    assert author.display_name == "Jaroslaw Oleradzki"
    assert author.affiliations[0].name == "Poznan University of Economics"
    assert author.affiliations[0].country_code == "PL"
