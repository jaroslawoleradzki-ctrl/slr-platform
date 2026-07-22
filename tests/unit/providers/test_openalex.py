import httpx
import pytest

from app.providers.openalex import OpenAlexClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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


@pytest.mark.anyio
async def test_iterate_works_follows_cursors_and_preserves_order() -> None:
    requested_cursors: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params["cursor"]
        requested_cursors.append(cursor)
        if cursor == "*":
            return httpx.Response(
                200,
                json={
                    "meta": {"next_cursor": "cursor-2"},
                    "results": [{"id": "W1"}, {"id": "W2"}],
                },
            )
        assert cursor == "cursor-2"
        return httpx.Response(
            200,
            json={
                "meta": {"next_cursor": None},
                "results": [{"id": "W3"}],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean")]

    assert requested_cursors == ["*", "cursor-2"]
    assert works == [{"id": "W1"}, {"id": "W2"}, {"id": "W3"}]


@pytest.mark.anyio
async def test_iterate_works_stops_after_first_page_without_next_cursor() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": [{"id": "W1"}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean")]

    assert request_count == 1
    assert works == [{"id": "W1"}]


@pytest.mark.anyio
async def test_iterate_works_propagates_http_error_from_later_page() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["cursor"] == "*":
            return httpx.Response(
                200,
                json={
                    "meta": {"next_cursor": "cursor-2"},
                    "results": [{"id": "W1"}],
                },
            )
        return httpx.Response(503, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(http_client=http_client)
        with pytest.raises(httpx.HTTPStatusError):
            _ = [work async for work in client.iterate_works("lean")]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"meta": {"next_cursor": None}}, "results must be a list"),
        ({"results": []}, "meta must be a JSON object"),
        (
            {"meta": {"next_cursor": ""}, "results": []},
            "next_cursor must be a non-blank string or null",
        ),
    ],
)
async def test_iterate_works_rejects_malformed_pagination_payload(
    payload: dict[str, object],
    message: str,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload, request=request)
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(http_client=http_client)
        with pytest.raises(ValueError, match=message):
            _ = [work async for work in client.iterate_works("lean")]
