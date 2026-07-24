import httpx
import pytest

from app.providers.semantic_scholar import SemanticScholarClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_search_papers_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph/v1/paper/search"
        assert request.url.params["query"] == "lean manufacturing"
        assert request.url.params["limit"] == "15"
        assert request.url.params["offset"] == "5"
        assert request.url.params["fields"] == "title,year,authors"
        assert "x-api-key" not in request.headers

        return httpx.Response(
            200,
            json={
                "total": 1,
                "offset": 5,
                "data": [
                    {
                        "paperId": "abc-123",
                        "title": "Lean Manufacturing Study",
                        "year": 2024,
                    }
                ]
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(http_client=http_client)
        papers = await client.search_papers(
            "  lean manufacturing  ",
            limit=15,
            offset=5,
            fields=["title", "  year  ", "authors"],
        )

    assert len(papers) == 1
    assert papers[0]["paperId"] == "abc-123"
    assert papers[0]["title"] == "Lean Manufacturing Study"


@pytest.mark.anyio
async def test_search_papers_api_key() -> None:
    async def handler_with_key(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "my-secret-token"
        return httpx.Response(200, json={"data": []}, request=request)

    # API key provided
    transport = httpx.MockTransport(handler_with_key)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(http_client=http_client, api_key="  my-secret-token  ")
        papers = await client.search_papers("lean")
    assert papers == []

    # Missing API key
    async def handler_no_key(request: httpx.Request) -> httpx.Response:
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json={"data": []}, request=request)

    transport_no = httpx.MockTransport(handler_no_key)
    async with httpx.AsyncClient(transport=transport_no) as http_client:
        client = SemanticScholarClient(http_client=http_client, api_key=None)
        papers = await client.search_papers("lean")
    assert papers == []


@pytest.mark.anyio
async def test_search_papers_without_fields() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "fields" not in request.url.params
        return httpx.Response(200, json={"data": []}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(http_client=http_client)
        papers = await client.search_papers("lean", fields=None)
    assert papers == []


@pytest.mark.anyio
async def test_search_papers_empty_or_missing_data() -> None:
    # missing data field
    async def handler_missing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total": 0}, request=request)

    transport_missing = httpx.MockTransport(handler_missing)
    async with httpx.AsyncClient(transport=transport_missing) as http_client:
        client = SemanticScholarClient(http_client=http_client)
        papers = await client.search_papers("lean")
    assert papers == []

    # null data field
    async def handler_null(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": None}, request=request)

    transport_null = httpx.MockTransport(handler_null)
    async with httpx.AsyncClient(transport=transport_null) as http_client:
        client = SemanticScholarClient(http_client=http_client)
        papers = await client.search_papers("lean")
    assert papers == []


@pytest.mark.anyio
async def test_search_papers_http_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SemanticScholarClient(http_client=http_client)
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_papers("lean")


@pytest.mark.anyio
async def test_search_papers_validation() -> None:
    async with httpx.AsyncClient() as http_client:
        client = SemanticScholarClient(http_client=http_client)

        # Blank or invalid query
        with pytest.raises(ValueError, match="query must not be blank"):
            await client.search_papers("  ")
        with pytest.raises(ValueError, match="query must not be blank"):
            await client.search_papers(None)  # type: ignore

        # Invalid limits
        with pytest.raises(ValueError, match="limit must be positive"):
            await client.search_papers("lean", limit=0)
        with pytest.raises(ValueError, match="limit must be positive"):
            await client.search_papers("lean", limit=-10)
        with pytest.raises(ValueError, match="limit must be positive"):
            await client.search_papers("lean", limit=True)  # type: ignore

        # Invalid offsets
        with pytest.raises(ValueError, match="offset must not be negative"):
            await client.search_papers("lean", offset=-1)
        with pytest.raises(ValueError, match="offset must not be negative"):
            await client.search_papers("lean", offset=False)  # type: ignore

        # Empty fields
        with pytest.raises(ValueError, match="fields must not be empty"):
            await client.search_papers("lean", fields=[])
        with pytest.raises(ValueError, match="fields must contain non-blank strings"):
            await client.search_papers("lean", fields=["title", "  "])


def test_client_init_blank_api_key() -> None:
    with httpx.Client() as http_client:
        with pytest.raises(ValueError, match="api_key must not be blank"):
            SemanticScholarClient(http_client=http_client, api_key="  ")  # type: ignore
