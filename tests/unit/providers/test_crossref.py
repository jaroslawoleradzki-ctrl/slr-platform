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
