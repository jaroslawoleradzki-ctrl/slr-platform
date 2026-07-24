import asyncio
from typing import Any, cast

import httpx
import pytest

from app.providers.crossref import CrossrefClient

_SUCCESS_PAYLOAD = {
    "status": "ok",
    "message-type": "work-list",
    "message": {"items": []},
}


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    async def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.advance(seconds)
        await asyncio.sleep(0)


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
        client = CrossrefClient(
            http_client=http_client,
            retry_attempts=1,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_works("lean")

    assert request_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
async def test_search_works_retries_supported_status_codes(
    status_code: int,
) -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            status_code,
            headers={"X-Attempt": str(request_count)},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.search_works("lean")

    assert request_count == 3
    assert exc_info.value.response.headers["X-Attempt"] == "3"


@pytest.mark.anyio
async def test_search_works_succeeds_after_retryable_status() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        payload = await client.search_works("lean")

    assert request_count == 2
    assert payload == _SUCCESS_PAYLOAD


@pytest.mark.anyio
async def test_search_works_retries_request_error_then_succeeds() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        payload = await client.search_works("lean")

    assert request_count == 2
    assert payload == _SUCCESS_PAYLOAD


@pytest.mark.anyio
async def test_search_works_propagates_last_request_error_after_retries() -> None:
    errors: list[httpx.RequestError] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        error = httpx.ConnectError("connection failed", request=request)
        errors.append(error)
        raise error

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(httpx.RequestError) as exc_info:
            await client.search_works("lean")

    assert len(errors) == 3
    assert exc_info.value is errors[-1]


@pytest.mark.anyio
async def test_search_works_does_not_retry_non_retryable_status() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(400, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_works("lean")

    assert request_count == 1


@pytest.mark.anyio
async def test_client_rejects_zero_retry_attempts() -> None:
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(
            ValueError,
            match="retry_attempts must be at least 1",
        ):
            CrossrefClient(http_client=http_client, retry_attempts=0)


@pytest.mark.anyio
async def test_client_rejects_boolean_retry_attempts() -> None:
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(
            TypeError,
            match="retry_attempts must be an integer",
        ):
            CrossrefClient(http_client=http_client, retry_attempts=True)


@pytest.mark.anyio
async def test_disabled_rate_limiter_does_not_sleep() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=None,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("first")
        await client.search_works("second")

    assert fake_time.sleep_calls == []
    assert request_start_times == [0.0, 0.0]


@pytest.mark.anyio
async def test_rate_limiter_does_not_delay_first_request() -> None:
    fake_time = FakeTime()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_SUCCESS_PAYLOAD,
            request=request,
        )
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=2,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("lean")

    assert fake_time.sleep_calls == []


@pytest.mark.anyio
async def test_rate_limiter_delays_immediate_second_request() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=2,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("first")
        await client.search_works("second")

    assert fake_time.sleep_calls == [pytest.approx(0.5)]
    assert request_start_times == [0.0, 0.5]


@pytest.mark.anyio
async def test_rate_limiter_does_not_delay_after_full_interval() -> None:
    fake_time = FakeTime()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_SUCCESS_PAYLOAD,
            request=request,
        )
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=2,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("first")
        fake_time.advance(0.5)
        await client.search_works("second")

    assert fake_time.sleep_calls == []


@pytest.mark.anyio
async def test_retry_attempts_are_rate_limited() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        if len(request_start_times) < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=4,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("lean")

    assert fake_time.sleep_calls == [
        pytest.approx(0.25),
        pytest.approx(0.25),
    ]
    assert request_start_times == [0.0, 0.25, 0.5]


@pytest.mark.anyio
async def test_concurrent_requests_reserve_distinct_start_times() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=10,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("first")
        await asyncio.gather(
            client.search_works("second"),
            client.search_works("third"),
        )

    assert fake_time.sleep_calls == [
        pytest.approx(0.1),
        pytest.approx(0.1),
    ]
    assert request_start_times == [0.0, 0.1, 0.2]


@pytest.mark.anyio
async def test_rate_limit_lock_is_released_before_http_io() -> None:
    fake_time = FakeTime()
    first_request_started = asyncio.Event()
    second_request_started = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["query"] == "first":
            first_request_started.set()
            await second_request_started.wait()
        else:
            second_request_started.set()
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=10,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        first_request = asyncio.create_task(client.search_works("first"))
        await first_request_started.wait()
        second_request = asyncio.create_task(client.search_works("second"))
        await asyncio.gather(first_request, second_request)

    assert fake_time.sleep_calls == [pytest.approx(0.1)]


@pytest.mark.anyio
async def test_rate_limiter_state_is_per_client_instance() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        return httpx.Response(200, json=_SUCCESS_PAYLOAD, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        first_client = CrossrefClient(
            http_client=http_client,
            requests_per_second=1,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        second_client = CrossrefClient(
            http_client=http_client,
            requests_per_second=1,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await first_client.search_works("first")
        await second_client.search_works("second")

    assert fake_time.sleep_calls == []
    assert request_start_times == [0.0, 0.0]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "requests_per_second",
    [0, -1, float("inf"), float("-inf"), float("nan")],
)
async def test_client_rejects_invalid_rate_limit(
    requests_per_second: float,
) -> None:
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(
            ValueError,
            match=(
                "requests_per_second must be a finite positive number or None"
            ),
        ):
            CrossrefClient(
                http_client=http_client,
                requests_per_second=requests_per_second,
            )


@pytest.mark.anyio
async def test_client_rejects_boolean_rate_limit() -> None:
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(
            TypeError,
            match="requests_per_second must be a number or None",
        ):
            CrossrefClient(http_client=http_client, requests_per_second=True)


@pytest.mark.anyio
async def test_search_works_rejects_non_object_root() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json=[], request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(
            ValueError,
            match="Crossref response must be a JSON object",
        ):
            await client.search_works("lean")

    assert request_count == 1


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


@pytest.mark.anyio
async def test_iterate_works_follows_cursors_and_preserves_order() -> None:
    requested_cursors: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        assert cursor is not None
        requested_cursors.append(cursor)
        if cursor == "*":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "next-cursor": "cursor-2",
                        "items": [{"DOI": "10.1000/1"}, {"DOI": "10.1000/2"}],
                    }
                },
                request=request,
            )
        assert cursor == "cursor-2"
        return httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": "cursor-3",
                    "items": [{"DOI": "10.1000/3"}],
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean", limit=3)]

    assert requested_cursors == ["*", "cursor-2"]
    assert works == [{"DOI": "10.1000/1"}, {"DOI": "10.1000/2"}, {"DOI": "10.1000/3"}]


@pytest.mark.anyio
async def test_iterate_works_stops_on_empty_items() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": "cursor-2",
                    "items": [],
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean")]

    assert request_count == 1
    assert works == []


@pytest.mark.anyio
async def test_iterate_works_stops_on_missing_or_null_next_cursor() -> None:
    # Test missing next-cursor
    async def handler_missing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [{"DOI": "10.1000/1"}],
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler_missing)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean")]
    assert works == [{"DOI": "10.1000/1"}]

    # Test null next-cursor
    async def handler_null(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": None,
                    "items": [{"DOI": "10.1000/2"}],
                }
            },
            request=request,
        )

    transport_null = httpx.MockTransport(handler_null)
    async with httpx.AsyncClient(transport=transport_null) as http_client:
        client = CrossrefClient(http_client=http_client)
        works_null = [work async for work in client.iterate_works("lean")]
    assert works_null == [{"DOI": "10.1000/2"}]


@pytest.mark.anyio
async def test_iterate_works_prevents_infinite_loop_on_duplicate_cursor() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": "same-cursor",
                    "items": [{"DOI": f"10.1000/{request_count}"}],
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean")]

    assert request_count == 2
    assert len(works) == 2


@pytest.mark.anyio
async def test_iterate_works_rejects_invalid_limit() -> None:
    async with httpx.AsyncClient() as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(TypeError, match="limit must be an integer or None"):
            async for _ in client.iterate_works("lean", limit=cast(Any, "ten")):
                pass
        with pytest.raises(TypeError, match="limit must be an integer or None"):
            async for _ in client.iterate_works("lean", limit=cast(Any, True)):
                pass
        with pytest.raises(ValueError, match="limit must be at least 1"):
            async for _ in client.iterate_works("lean", limit=0):
                pass


@pytest.mark.anyio
async def test_iterate_works_stops_exactly_at_limit_without_fetching_next_page() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": f"cursor-{request_count + 1}",
                    "items": [{"DOI": f"10.1000/{i}"} for i in range(1, 11)],
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean", rows=10, limit=15)]

    assert request_count == 2
    assert len(works) == 15
    assert [w["DOI"] for w in works] == [f"10.1000/{i}" for i in range(1, 11)] + [f"10.1000/{i}" for i in range(1, 6)]


@pytest.mark.anyio
async def test_iterate_works_rate_limiting_between_pages() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        cursor = request.url.params.get("cursor")
        next_cursor = "cursor-2" if cursor == "*" else None
        return httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": next_cursor,
                    "items": [{"DOI": "10.1000/1"}],
                }
            },
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            requests_per_second=2,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        _ = [work async for work in client.iterate_works("lean")]

    assert fake_time.sleep_calls == [pytest.approx(0.5)]
    assert request_start_times == [0.0, 0.5]


@pytest.mark.anyio
async def test_iterate_works_retries_during_pagination_then_succeeds() -> None:
    request_events: list[tuple[str, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        request_events.append((request.method, cursor))

        if cursor == "*":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "next-cursor": "cursor-2",
                        "items": [{"DOI": "10.1000/1"}],
                    }
                },
                request=request,
            )
        elif cursor == "cursor-2":
            cursor_2_count = sum(1 for _, c in request_events if c == "cursor-2")
            if cursor_2_count == 1:
                return httpx.Response(503, request=request)
            else:
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "next-cursor": None,
                            "items": [{"DOI": "10.1000/2"}],
                        }
                    },
                    request=request,
                )
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = CrossrefClient(
            http_client=http_client,
            retry_attempts=3,
        )
        works = [work async for work in client.iterate_works("lean")]

    assert request_events == [
        ("GET", "*"),
        ("GET", "cursor-2"),
        ("GET", "cursor-2"),
    ]
    assert len(request_events) == 3
    assert works == [{"DOI": "10.1000/1"}, {"DOI": "10.1000/2"}]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"message": {"next-cursor": 123, "items": []}},
            "Crossref response message.next-cursor must be a string",
        ),
        (
            {"message": {"next-cursor": "   ", "items": []}},
            "Crossref response message.next-cursor must not be blank",
        ),
    ],
)
async def test_search_works_rejects_malformed_next_cursor(
    payload: dict[str, Any],
    message: str,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload, request=request)
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(ValueError, match=message):
            await client.search_works("lean", cursor="*")


@pytest.mark.anyio
async def test_search_works_ignores_next_cursor_when_cursor_is_none() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"message": {"next-cursor": 123, "items": []}},
            request=request,
        )
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        payload = await client.search_works("lean", cursor=None)
    assert payload["message"]["next-cursor"] == 123


@pytest.mark.anyio
async def test_iterate_works_rejects_non_object_work() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": "cursor-2",
                    "items": [{"DOI": "10.1000/1"}, "not-a-dict"],
                }
            },
            request=request,
        )
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        with pytest.raises(ValueError, match="Crossref work must be a JSON object"):
            async for _ in client.iterate_works("lean"):
                pass


@pytest.mark.anyio
async def test_iterate_works_passes_special_characters_cursor_properly() -> None:
    special_cursor = "cursor with spaces+and/slashes=="
    requested_cursors: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        assert cursor is not None
        requested_cursors.append(cursor)
        if cursor == "*":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "next-cursor": special_cursor,
                        "items": [{"DOI": "10.1000/1"}],
                    }
                },
                request=request,
            )
        assert cursor == special_cursor
        return httpx.Response(
            200,
            json={
                "message": {
                    "next-cursor": None,
                    "items": [{"DOI": "10.1000/2"}],
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CrossrefClient(http_client=http_client)
        works = [work async for work in client.iterate_works("lean")]

    assert requested_cursors == ["*", special_cursor]
    assert works == [{"DOI": "10.1000/1"}, {"DOI": "10.1000/2"}]
