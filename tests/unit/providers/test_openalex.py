import httpx
import pytest

from app.providers.openalex import OpenAlexClient


@pytest.mark.anyio
async def test_search_works_sends_expected_request() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/works"
        assert request.url.params["search"] == "lean energy efficiency"
        assert request.url.params["per-page"] == "50"
        assert request.url.params["cursor"] == "next-cursor"
        assert request.url.params["mailto"] == "researcher@example.org"
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": [{"id": "W1"}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            mailto=" researcher@example.org ",
        )
        payload = await client.search_works(
            "  lean energy efficiency  ",
            per_page=50,
            cursor="next-cursor",
        )

    assert payload["results"] == [{"id": "W1"}]


@pytest.mark.anyio
async def test_search_works_raises_for_http_errors() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, request=request)
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(http_client=http_client)
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_works("lean")


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["", "   "])
async def test_search_works_rejects_blank_query(query: str) -> None:
    async with httpx.AsyncClient() as http_client:
        client = OpenAlexClient(http_client=http_client)
        with pytest.raises(ValueError, match="query must not be blank"):
            await client.search_works(query)


@pytest.mark.anyio
@pytest.mark.parametrize("per_page", [0, 201])
async def test_search_works_rejects_invalid_page_size(per_page: int) -> None:
    async with httpx.AsyncClient() as http_client:
        client = OpenAlexClient(http_client=http_client)
        with pytest.raises(ValueError, match="per_page must be between 1 and 200"):
            await client.search_works("lean", per_page=per_page)


@pytest.mark.anyio
async def test_client_rejects_blank_mailto() -> None:
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(ValueError, match="mailto must not be blank"):
            OpenAlexClient(http_client=http_client, mailto="   ")
