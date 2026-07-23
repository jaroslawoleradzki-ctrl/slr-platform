import asyncio
from typing import TypedDict

import httpx
import pytest

from app.providers.openalex import OpenAlexClient


class RetryConfiguration(TypedDict, total=False):
    max_attempts: int
    retry_wait_multiplier: float
    retry_wait_max: float


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
async def test_rate_limiter_does_not_delay_first_request() -> None:
    fake_time = FakeTime()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": []},
            request=request,
        )
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(
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
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": []},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            requests_per_second=2,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("lean")
        await client.search_works("energy")

    assert fake_time.sleep_calls == [pytest.approx(0.5)]
    assert request_start_times == [0.0, 0.5]


@pytest.mark.anyio
async def test_rate_limiter_does_not_delay_after_minimum_interval() -> None:
    fake_time = FakeTime()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": []},
            request=request,
        )
    )

    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            requests_per_second=2,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("lean")
        fake_time.advance(0.5)
        await client.search_works("energy")

    assert fake_time.sleep_calls == []


@pytest.mark.anyio
async def test_rate_limiter_can_be_disabled() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": []},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            requests_per_second=None,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("lean")
        await client.search_works("energy")

    assert fake_time.sleep_calls == []
    assert request_start_times == [0.0, 0.0]


@pytest.mark.anyio
@pytest.mark.parametrize("requests_per_second", [0, -1])
async def test_client_rejects_non_positive_rate_limit(
    requests_per_second: float,
) -> None:
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(
            ValueError,
            match="requests_per_second must be positive or None",
        ):
            OpenAlexClient(
                http_client=http_client,
                requests_per_second=requests_per_second,
            )


@pytest.mark.anyio
async def test_retry_attempts_are_rate_limited() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        if len(request_start_times) == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": []},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            max_attempts=2,
            retry_wait_multiplier=0,
            requests_per_second=4,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        await client.search_works("lean")

    assert fake_time.sleep_calls == [pytest.approx(0.25)]
    assert request_start_times == [0.0, 0.25]


@pytest.mark.anyio
async def test_cursor_pages_are_rate_limited() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        next_cursor = (
            "cursor-2" if request.url.params["cursor"] == "*" else None
        )
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": next_cursor}, "results": []},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            requests_per_second=5,
            clock=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
        _ = [work async for work in client.iterate_works("lean")]

    assert fake_time.sleep_calls == [pytest.approx(0.2)]
    assert request_start_times == [0.0, 0.2]


@pytest.mark.anyio
async def test_concurrent_requests_reserve_distinct_start_times() -> None:
    fake_time = FakeTime()
    request_start_times: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        request_start_times.append(fake_time.monotonic())
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": []},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = OpenAlexClient(
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
async def test_search_works_retries_retryable_status_then_succeeds() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": [{"id": "W1"}]},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            max_attempts=3,
            retry_wait_multiplier=0,
            requests_per_second=None,
        )
        payload = await client.search_works("lean")

    assert request_count == 3
    assert payload["results"] == [{"id": "W1"}]


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
async def test_search_works_retries_supported_status_codes(status_code: int) -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(status_code, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            max_attempts=3,
            retry_wait_multiplier=0,
            requests_per_second=None,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_works("lean")

    assert request_count == 3


@pytest.mark.anyio
async def test_search_works_does_not_retry_non_retryable_status() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(400, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            max_attempts=3,
            retry_wait_multiplier=0,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_works("lean")

    assert request_count == 1


@pytest.mark.anyio
async def test_search_works_retries_transport_errors() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": []},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAlexClient(
            http_client=http_client,
            max_attempts=2,
            retry_wait_multiplier=0,
            requests_per_second=None,
        )
        payload = await client.search_works("lean")

    assert request_count == 2
    assert payload["results"] == []


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
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_attempts": 0}, "max_attempts must be at least 1"),
        (
            {"retry_wait_multiplier": -1},
            "retry_wait_multiplier must not be negative",
        ),
        ({"retry_wait_max": -1}, "retry_wait_max must not be negative"),
    ],
)
async def test_client_rejects_invalid_retry_configuration(
    kwargs: RetryConfiguration,
    message: str,
) -> None:
    async with httpx.AsyncClient() as http_client:
        with pytest.raises(ValueError, match=message):
            OpenAlexClient(http_client=http_client, **kwargs)


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
        client = OpenAlexClient(
            http_client=http_client,
            requests_per_second=None,
        )
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
        client = OpenAlexClient(
            http_client=http_client,
            max_attempts=2,
            retry_wait_multiplier=0,
            requests_per_second=None,
        )
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
