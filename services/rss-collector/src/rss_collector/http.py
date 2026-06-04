from __future__ import annotations

from dataclasses import dataclass

import httpx

from .models import PollingSource


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    body: bytes
    etag: str | None
    last_modified: str | None


def request_headers(source: PollingSource, user_agent: str) -> dict[str, str]:
    headers = {"User-Agent": str(source.source_config.get("user_agent") or user_agent)}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified
    return headers


async def fetch_source(client: httpx.AsyncClient, source: PollingSource, user_agent: str, timeout_seconds: int) -> FetchResult:
    response = await client.get(
        source.handle_or_url,
        headers=request_headers(source, user_agent),
        timeout=timeout_seconds,
        follow_redirects=True,
    )
    return FetchResult(
        status_code=response.status_code,
        body=response.content,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )
