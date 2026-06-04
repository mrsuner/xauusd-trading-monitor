from __future__ import annotations

import httpx
import pytest

from x_publisher.providers import XProvider
from x_publisher.settings import Settings


def make_settings(**overrides: object) -> Settings:
    data = {
        "DATABASE_URL": "postgresql://x:y@localhost/db",
        "X_API_KEY": "key",
        "X_API_SECRET": "secret",
        "X_ACCESS_TOKEN": "token",
        "X_ACCESS_TOKEN_SECRET": "token-secret",
        "X_API_BASE_URL": "https://api.twitter.test/2",
    }
    data.update(overrides)
    return Settings(**data)


@pytest.mark.asyncio
async def test_provider_sends_post_with_oauth_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"data": {"id": "123", "text": "hello"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await XProvider(settings=make_settings(), client=client).send("hello")

    assert result.success is True
    assert requests[0].url.path == "/2/tweets"
    assert requests[0].headers["authorization"].startswith("OAuth ")
    assert requests[0].read() == b'{"text":"hello"}'


@pytest.mark.asyncio
async def test_provider_requires_oauth1_credentials() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        result = await XProvider(
            settings=make_settings(X_ACCESS_TOKEN_SECRET=""),
            client=client,
        ).send("hello")

    assert result.success is False
    assert result.is_transient is False
    assert result.error_message == "missing_x_oauth1_config"


@pytest.mark.asyncio
async def test_provider_classifies_rate_limit_as_transient() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "60"}, json={"title": "Too Many Requests"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await XProvider(settings=make_settings(), client=client).send("hello")

    assert result.success is False
    assert result.is_transient is True
    assert result.retry_after_seconds == 60
