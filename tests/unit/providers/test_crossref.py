from typing import Any, cast

import httpx
import pytest

from app.providers.crossref import CrossrefClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_search_works_sends_expected_request_without_cursor() -> None:
    expected_payload = {
        "status": "ok",
        "message-type": "work-list",
        "message": {"items": [{"DOI": "10.1000/example"}]},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/works"
        assert request.url.params["query"] == "lean energy"
        assert request.url.params["rows"] == "50"
        assert "cursor" not in request.url.params
        assert request.headers["User-Agent"].startswith("slr-platform/0.1.0")
        return httpx.Response(200, json=expected_payload, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        payload = await client.search_works("  lean energy  ", rows=50)

    assert payload == expected_payload


@pytest.mark.anyio
async def test_search_works_sends_cursor_when_provided() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["rows"] == "20"
        assert request.url.params["cursor"] == "next-cursor"
        return httpx.Response(
            200,
            json={"message": {"items": []}},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        await client.search_works("lean", cursor="  next-cursor  ")


@pytest.mark.anyio
async def test_client_uses_configured_base_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "crossref.example"
        assert request.url.path == "/api/works"
        return httpx.Response(
            200,
            json={"message": {"items": []}},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            base_url="https://crossref.example/api/",
        )
        await client.search_works("lean")


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["", "   "])
async def test_search_works_rejects_blank_query(query: str) -> None:
    async with httpx.AsyncClient() as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(ValueError, match="query must not be blank"):
            await client.search_works(query)


@pytest.mark.anyio
async def test_search_works_rejects_non_string_query() -> None:
    async with httpx.AsyncClient() as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(TypeError, match="query must be a string"):
            await client.search_works(cast(Any, 42))


@pytest.mark.anyio
@pytest.mark.parametrize("rows", [0, 1001])
async def test_search_works_rejects_rows_outside_range(rows: int) -> None:
    async with httpx.AsyncClient() as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(ValueError, match="rows must be between 1 and 1000"):
            await client.search_works("lean", rows=rows)


@pytest.mark.anyio
@pytest.mark.parametrize("rows", [True, 20.5, "20"])
async def test_search_works_rejects_non_integer_rows(rows: object) -> None:
    async with httpx.AsyncClient() as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(TypeError, match="rows must be an integer"):
            await client.search_works("lean", rows=cast(Any, rows))


@pytest.mark.anyio
@pytest.mark.parametrize("cursor", ["", "   "])
async def test_search_works_rejects_blank_cursor(cursor: str) -> None:
    async with httpx.AsyncClient() as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(ValueError, match="cursor must not be blank"):
            await client.search_works("lean", cursor=cursor)


@pytest.mark.anyio
async def test_search_works_rejects_non_string_cursor() -> None:
    async with httpx.AsyncClient() as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(TypeError, match="cursor must be a string or None"):
            await client.search_works("lean", cursor=cast(Any, 42))


@pytest.mark.anyio
async def test_search_works_propagates_http_status_error_without_retry() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_works("lean")

    assert request_count == 1


@pytest.mark.anyio
async def test_search_works_rejects_non_object_root() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=[], request=request)
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(
            ValueError,
            match="Crossref response must be a JSON object",
        ):
            await client.search_works("lean")


@pytest.mark.anyio
async def test_search_works_rejects_non_object_message() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"message": []},
            request=request,
        )
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(
            ValueError,
            match="Crossref response message must be a JSON object",
        ):
            await client.search_works("lean")


@pytest.mark.anyio
async def test_search_works_rejects_non_list_items() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"message": {"items": {}}},
            request=request,
        )
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(
            ValueError,
            match="Crossref response message.items must be a list",
        ):
            await client.search_works("lean")
